from datetime import datetime

from pydantic import BaseModel, Field

from src.conversations.models import Conversation, Message


class ChatResponse(BaseModel):
    conversation_id: str
    response: str
    sources: list[dict[str, object]] = Field(default_factory=list)
    request_id: str
    duration_ms: float


class ConversationSummary(BaseModel):
    id: str
    title: str | None
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationDetailResponse(Conversation):
    pass


class MessageResponse(Message):
    pass
