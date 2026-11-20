import os

import pytest

for _variable in (
    "MCP_AUTH_TOKEN",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
):
    os.environ[_variable] = ""

from src.main import app
from src.security.rate_limit import build_rate_limiter


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    app.state.conversation_repository = __import__(
        "src.conversations.memory_repository", fromlist=["InMemoryConversationRepository"]
    ).InMemoryConversationRepository()
    app.state.rate_limiter = build_rate_limiter("")
    with TestClient(app) as test_client:
        yield test_client
