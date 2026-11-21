from datetime import datetime

from pydantic import BaseModel, Field

from src.conversations.models import Conversation, Message
from src.core.sources import SourceRef


class ChatResponse(BaseModel):
    conversation_id: str
    response: str
    request_id: str
    duration_ms: float
    # Fontes consultadas nesta resposta (nome, data da consulta, a que momento o dado se refere).
    sources: list[SourceRef] = Field(default_factory=list)


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
