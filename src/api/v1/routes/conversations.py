from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.dependencies import get_owner_id, rate_limit_read

from src.api.schemas import ConversationDetailResponse, ConversationSummary
from src.conversations.memory_repository import InMemoryConversationRepository

router = APIRouter(
    prefix="/conversations",
    tags=["conversations"],
    dependencies=[Depends(rate_limit_read)],
)


def get_repository(request: Request) -> InMemoryConversationRepository:
    return request.app.state.conversation_repository


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    repository: InMemoryConversationRepository = Depends(get_repository),
    owner_id: str = Depends(get_owner_id),
) -> list[ConversationSummary]:
    conversations = await repository.list(owner_id)
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
    owner_id: str = Depends(get_owner_id),
) -> ConversationDetailResponse:
    conversation = await repository.get(conversation_id, owner_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return ConversationDetailResponse(**conversation.model_dump())


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    repository: InMemoryConversationRepository = Depends(get_repository),
    owner_id: str = Depends(get_owner_id),
) -> None:
    if not await repository.delete(conversation_id, owner_id):
        raise HTTPException(status_code=404, detail="conversation not found")
