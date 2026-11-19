from time import perf_counter

import structlog
from fastapi import APIRouter, Depends, Request
from langchain_core.messages import AIMessage, HumanMessage

from src.api.schemas import ChatResponse
from src.agent.graph import OceanAgent
from src.conversations.memory_repository import InMemoryConversationRepository
from src.conversations.models import Message, MessageRole
from src.core.config import get_settings
from src.core.exceptions import ConfigurationError, GuardrailError, RetrievalError
from src.mcp.client import MCPClient
from src.security.validation import ChatRequest

router = APIRouter(tags=["chat"])
logger = structlog.get_logger()


def get_repository(request: Request) -> InMemoryConversationRepository:
    return request.app.state.conversation_repository


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    repository: InMemoryConversationRepository = Depends(get_repository),
) -> ChatResponse:
    started = perf_counter()
    settings = get_settings()
    logger.info("request.received", stage="request_received")

    try:
        if payload.conversation_id:
            conversation = await repository.get(payload.conversation_id)
            if conversation is None:
                raise GuardrailError("conversation_id does not exist")
        else:
            conversation = await repository.create()

        history = [
            HumanMessage(content=item.content)
            if item.role is MessageRole.USER
            else AIMessage(content=item.content)
            for item in conversation.messages
            if item.role in (MessageRole.USER, MessageRole.ASSISTANT)
        ]
        await repository.add_message(
            conversation.id,
            Message(role=MessageRole.USER, content=payload.message),
        )
        logger.info("agent.started", stage="agent_started", conversation_id=conversation.id)

        agent = OceanAgent(settings, MCPClient(settings))
        response_text = await agent.run(payload.message, history=history)
        sources = agent.last_result.sources

        await repository.add_message(
            conversation.id,
            Message(role=MessageRole.ASSISTANT, content=response_text),
        )
        duration_ms = round((perf_counter() - started) * 1000, 2)
        logger.info(
            "response.completed",
            stage="response_completed",
            conversation_id=conversation.id,
            duration_ms=duration_ms,
        )
        return ChatResponse(
            conversation_id=conversation.id,
            response=response_text,
            sources=sources,
            request_id=request.state.request_id,
            duration_ms=duration_ms,
        )
    except GuardrailError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConfigurationError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RetrievalError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail=str(exc)) from exc
