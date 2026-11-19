from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.schemas import ConversationDetailResponse, ConversationSummary
from src.conversations.memory_repository import InMemoryConversationRepository

router = APIRouter(prefix="/conversations", tags=["conversations"])


def get_repository(request: Request) -> InMemoryConversationRepository:
    return request.app.state.conversation_repository


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    repository: InMemoryConversationRepository = Depends(get_repository),
) -> list[ConversationSummary]:
    conversations = await repository.list()
    return [
        ConversationSummary(
            id=item.id,
            title=item.title,
            message_count=len(item.messages),
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in conversations
    ]


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    repository: InMemoryConversationRepository = Depends(get_repository),
) -> ConversationDetailResponse:
    conversation = await repository.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return ConversationDetailResponse(**conversation.model_dump())


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    repository: InMemoryConversationRepository = Depends(get_repository),
) -> None:
    if not await repository.delete(conversation_id):
        raise HTTPException(status_code=404, detail="conversation not found")
