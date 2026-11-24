from time import perf_counter

import structlog
from fastapi import APIRouter, Depends, Request
from langchain_core.messages import AIMessage, HumanMessage

from src.api.dependencies import get_owner_id, rate_limit_chat
from src.api.schemas import ChatResponse
from src.agent.graph import OceanAgent
from src.conversations.memory_repository import InMemoryConversationRepository
from src.conversations.models import Message, MessageRole
from src.core.config import get_settings
from src.core.exceptions import ConfigurationError, GuardrailError
from src.mcp.client import MCPClient
from src.observability.tracing import trace_request
from src.security.guardrails import is_blocked, validate_user_message
from src.security.validation import ChatRequest

router = APIRouter(tags=["chat"])
logger = structlog.get_logger()


def get_repository(request: Request) -> InMemoryConversationRepository:
    return request.app.state.conversation_repository


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(rate_limit_chat)])
async def chat(
    payload: ChatRequest,
    request: Request,
    repository: InMemoryConversationRepository = Depends(get_repository),
    owner_id: str = Depends(get_owner_id),
) -> ChatResponse:
    started = perf_counter()
    settings = get_settings()
    logger.info("request.received", stage="request_received")

    try:
        # Valida antes de criar conversa ou gravar qualquer coisa: mensagem bloqueada não pode
        # ficar no histórico, senão voltaria ao modelo nas próximas perguntas.
        validate_user_message(payload.message)
        if payload.conversation_id:
            conversation = await repository.get(payload.conversation_id, owner_id)
            if conversation is None:
                raise GuardrailError("conversation_id does not exist")
        else:
            conversation = await repository.create(owner_id)

        history = [
            HumanMessage(content=item.content)
            if item.role is MessageRole.USER
            else AIMessage(content=item.content)
            for item in conversation.messages
            if item.role in (MessageRole.USER, MessageRole.ASSISTANT)
            and not (item.role is MessageRole.USER and is_blocked(item.content))
        ]
        await repository.add_message(
            conversation.id,
            Message(role=MessageRole.USER, content=payload.message),
        )
        logger.info("agent.started", stage="agent_started", conversation_id=conversation.id)

        agent = OceanAgent(settings, MCPClient(settings))
        with trace_request(
            name="ocean-chat",
            session_id=conversation.id,
            user_id=owner_id,
            input_text=None,
            tags=[settings.environment],
        ) as trace:
            result = await agent.run(payload.message, history=history)
            trace.set_output({"status": "completed", "source_count": len(result.sources)})

        sources = [source.model_dump(mode="json") for source in result.sources]
        await repository.add_message(
            conversation.id,
            Message(
                role=MessageRole.ASSISTANT,
                content=result.text,
                metadata={"sources": sources} if sources else {},
            ),
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
            response=result.text,
            request_id=request.state.request_id,
            duration_ms=duration_ms,
            sources=result.sources,
        )
    except GuardrailError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConfigurationError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail=str(exc)) from exc
