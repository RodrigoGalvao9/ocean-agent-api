from abc import ABC, abstractmethod

from src.conversations.models import Conversation, Message


class ConversationRepository(ABC):
    @abstractmethod
    async def create(self) -> Conversation: ...

    @abstractmethod
    async def get(self, conversation_id: str) -> Conversation | None: ...

    @abstractmethod
    async def list(self) -> list[Conversation]: ...

    @abstractmethod
    async def add_message(self, conversation_id: str, message: Message) -> Conversation: ...

    @abstractmethod
    async def delete(self, conversation_id: str) -> bool: ...
