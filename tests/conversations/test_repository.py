import pytest

from src.conversations.memory_repository import InMemoryConversationRepository
from src.conversations.models import Message, MessageRole


@pytest.mark.asyncio
async def test_in_memory_conversation_repository_crud():
    repository = InMemoryConversationRepository()
    conversation = await repository.create()
    await repository.add_message(
        conversation.id,
        Message(role=MessageRole.USER, content="hello"),
    )

    listed = await repository.list()
    assert len(listed) == 1
    retrieved = await repository.get(conversation.id)
    assert retrieved is not None
    assert retrieved.messages[0].content == "hello"
    assert await repository.delete(conversation.id)
    assert await repository.get(conversation.id) is None
