import pytest

from src.main import app


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    app.state.conversation_repository = __import__(
        "src.conversations.memory_repository", fromlist=["InMemoryConversationRepository"]
    ).InMemoryConversationRepository()
    return TestClient(app)
