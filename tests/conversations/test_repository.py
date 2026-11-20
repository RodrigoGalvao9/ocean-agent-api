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


@pytest.mark.asyncio
async def test_repository_enforces_owner_and_caps():
    from src.core.exceptions import GuardrailError

    repository = InMemoryConversationRepository(max_conversations=2, max_messages_per_conversation=1)
    first = await repository.create("alice")
    await repository.create("bob")
    assert await repository.get(first.id, "bob") is None
    assert not await repository.delete(first.id, "bob")

    await repository.add_message(first.id, Message(role=MessageRole.USER, content="1"))
    with pytest.raises(GuardrailError):
        await repository.add_message(first.id, Message(role=MessageRole.USER, content="2"))

    await repository.create("carol")  # passa de 2: a mais antiga sai
    assert len(await repository.list()) == 2
