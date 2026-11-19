from datetime import UTC, datetime

from src.conversations.models import Conversation, Message
from src.conversations.repository import ConversationRepository


class InMemoryConversationRepository(ConversationRepository):
    def __init__(self) -> None:
        self._conversations: dict[str, Conversation] = {}

    async def create(self) -> Conversation:
        conversation = Conversation()
        self._conversations[conversation.id] = conversation
        return conversation.model_copy(deep=True)

    async def get(self, conversation_id: str) -> Conversation | None:
        conversation = self._conversations.get(conversation_id)
        return conversation.model_copy(deep=True) if conversation else None

    async def list(self) -> list[Conversation]:
        return [conversation.model_copy(deep=True) for conversation in self._conversations.values()]

    async def add_message(self, conversation_id: str, message: Message) -> Conversation:
        conversation = self._conversations.get(conversation_id)
        if conversation is None:
            raise KeyError(conversation_id)
        conversation.messages.append(message)
        conversation.updated_at = datetime.now(UTC)
        return conversation.model_copy(deep=True)

    async def delete(self, conversation_id: str) -> bool:
        return self._conversations.pop(conversation_id, None) is not None
