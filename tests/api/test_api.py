from unittest.mock import AsyncMock, patch


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["X-Request-ID"]


def test_chat_creates_conversation_and_returns_metadata(client):
    with patch("src.api.v1.routes.chat.OceanAgent") as agent_cls:
        agent_cls.return_value.run = AsyncMock(return_value="Hello")
        with patch("src.api.v1.routes.chat.get_settings") as get_settings:
            get_settings.return_value.groq_api_key = "test"
            response = client.post("/api/v1/chat", json={"message": "Hi"})

    assert response.status_code == 200
    body = response.json()
    assert body["response"] == "Hello"
    assert body["conversation_id"]
    assert body["request_id"]
    assert body["duration_ms"] >= 0


def test_conversation_crud(client):
    list_response = client.get("/api/v1/conversations")
    assert list_response.status_code == 200
    assert list_response.json() == []

    with patch("src.api.v1.routes.chat.OceanAgent") as agent_cls:
        agent_cls.return_value.run = AsyncMock(return_value="Response")
        chat = client.post("/api/v1/chat", json={"message": "Create me"})

    conversation_id = chat.json()["conversation_id"]
    detail = client.get(f"/api/v1/conversations/{conversation_id}")
    assert detail.status_code == 200
    assert len(detail.json()["messages"]) == 2
    delete = client.delete(f"/api/v1/conversations/{conversation_id}")
    assert delete.status_code == 204
    assert client.get(f"/api/v1/conversations/{conversation_id}").status_code == 404
