from datetime import UTC, datetime

from src.conversations.models import Conversation, Message
from src.conversations.repository import ConversationRepository
from src.core.exceptions import GuardrailError


class InMemoryConversationRepository(ConversationRepository):
    def __init__(
        self,
        max_conversations: int = 1000,
        max_messages_per_conversation: int = 60,
    ) -> None:
        self._conversations: dict[str, Conversation] = {}
        self._max_conversations = max_conversations
        self._max_messages = max_messages_per_conversation

    def _visible(self, conversation: Conversation | None, owner_id: str | None) -> bool:
        return conversation is not None and (
            owner_id is None or conversation.owner_id == owner_id
        )

    def _evict_oldest(self) -> None:
        """Em API pública a memória não pode crescer sem limite: a conversa mais antiga sai."""
        while len(self._conversations) >= self._max_conversations:
            oldest = min(self._conversations.values(), key=lambda c: c.updated_at)
            del self._conversations[oldest.id]

    async def create(self, owner_id: str | None = None) -> Conversation:
        self._evict_oldest()
        conversation = Conversation(owner_id=owner_id)
        self._conversations[conversation.id] = conversation
        return conversation.model_copy(deep=True)

    async def get(self, conversation_id: str, owner_id: str | None = None) -> Conversation | None:
        conversation = self._conversations.get(conversation_id)
        if not self._visible(conversation, owner_id):
            return None
        return conversation.model_copy(deep=True)

    async def list(self, owner_id: str | None = None) -> list[Conversation]:
        items = [c for c in self._conversations.values() if self._visible(c, owner_id)]
        items.sort(key=lambda c: c.updated_at, reverse=True)
        return [c.model_copy(deep=True) for c in items]

    async def add_message(self, conversation_id: str, message: Message) -> Conversation:
        conversation = self._conversations.get(conversation_id)
        if conversation is None:
            raise KeyError(conversation_id)
        if len(conversation.messages) >= self._max_messages:
            raise GuardrailError(
                "esta conversa atingiu o limite de mensagens; inicie uma nova conversa"
            )
        conversation.messages.append(message)
        conversation.updated_at = datetime.now(UTC)
        return conversation.model_copy(deep=True)

    async def delete(self, conversation_id: str, owner_id: str | None = None) -> bool:
        conversation = self._conversations.get(conversation_id)
        if not self._visible(conversation, owner_id):
            return False
        del self._conversations[conversation_id]
        return True
