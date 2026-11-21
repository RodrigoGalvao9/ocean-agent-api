from unittest.mock import AsyncMock, patch

from src.agent.graph import AgentResult

import pytest

from src.core.config import Settings

CLIENT_A = {"X-Client-Id": "a" * 32}
CLIENT_B = {"X-Client-Id": "b" * 32}


def _chat(client, message="oi", headers=None, **extra):
    with patch("src.api.v1.routes.chat.OceanAgent") as agent_cls:
        agent_cls.return_value.run = AsyncMock(return_value=AgentResult("ok"))
        return client.post("/api/v1/chat", json={"message": message, **extra}, headers=headers or {})


@pytest.fixture
def tight_limits():
    settings = Settings(
        rate_limit_chat_per_minute=2,
        rate_limit_chat_per_day=100,
        rate_limit_global_per_minute=100,
        rate_limit_read_per_minute=3,
    )
    with patch("src.api.dependencies.get_settings", return_value=settings):
        yield settings


def test_chat_is_limited_per_ip_with_retry_after(client, tight_limits):
    assert _chat(client).status_code == 200
    assert _chat(client).status_code == 200
    blocked = _chat(client)
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    assert "Muitas requisições" in blocked.json()["detail"]


def test_rotating_client_id_does_not_bypass_the_ip_limit(client, tight_limits):
    assert _chat(client, headers={"X-Client-Id": "a" * 32}).status_code == 200
    assert _chat(client, headers={"X-Client-Id": "b" * 32}).status_code == 200
    assert _chat(client, headers={"X-Client-Id": "c" * 32}).status_code == 429


def test_global_limit_protects_the_llm_budget(client):
    settings = Settings(
        rate_limit_chat_per_minute=50,
        rate_limit_global_per_minute=2,
    )
    with patch("src.api.dependencies.get_settings", return_value=settings):
        assert _chat(client).status_code == 200
        assert _chat(client).status_code == 200
        assert _chat(client).status_code == 429


def test_read_endpoints_are_limited_too(client, tight_limits):
    for _ in range(3):
        assert client.get("/api/v1/conversations").status_code == 200
    assert client.get("/api/v1/conversations").status_code == 429


def test_rate_limit_can_be_disabled(client):
    settings = Settings(rate_limit_enabled=False, rate_limit_chat_per_minute=1)
    with patch("src.api.dependencies.get_settings", return_value=settings):
        assert all(_chat(client).status_code == 200 for _ in range(4))


def test_conversations_are_isolated_between_clients(client):
    conversation_id = _chat(client, headers=CLIENT_A).json()["conversation_id"]

    assert [c["id"] for c in client.get("/api/v1/conversations", headers=CLIENT_A).json()] == [
        conversation_id
    ]
    assert client.get("/api/v1/conversations", headers=CLIENT_B).json() == []
    assert client.get(f"/api/v1/conversations/{conversation_id}", headers=CLIENT_B).status_code == 404
    assert client.delete(f"/api/v1/conversations/{conversation_id}", headers=CLIENT_B).status_code == 404
    # B também não consegue continuar a conversa de A
    assert _chat(client, headers=CLIENT_B, conversation_id=conversation_id).status_code == 400
    assert client.get(f"/api/v1/conversations/{conversation_id}", headers=CLIENT_A).status_code == 200


def test_owner_id_is_never_exposed(client):
    conversation_id = _chat(client, headers=CLIENT_A).json()["conversation_id"]
    detail = client.get(f"/api/v1/conversations/{conversation_id}", headers=CLIENT_A).json()
    assert "owner_id" not in detail


def test_oversized_body_is_rejected(client):
    response = client.post(
        "/api/v1/chat",
        content=b"x" * 20_000,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413


def test_cors_allows_only_configured_origins(client):
    ok = client.options(
        "/api/v1/chat",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-client-id",
        },
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    blocked = client.options(
        "/api/v1/chat",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in blocked.headers


def test_429_still_carries_cors_headers(client, tight_limits):
    headers = {"Origin": "http://localhost:5173"}
    for _ in range(2):
        _chat(client, headers=headers)
    blocked = _chat(client, headers=headers)
    assert blocked.status_code == 429
    assert blocked.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_metrics_requires_token_in_production(client):
    prod = Settings(environment="production", metrics_token="")
    with patch("src.main.get_settings", return_value=prod):
        assert client.get("/metrics").status_code == 404
    secured = Settings(environment="production", metrics_token="s3cret")
    with patch("src.main.get_settings", return_value=secured):
        assert client.get("/metrics").status_code == 401
        assert client.get("/metrics", headers={"Authorization": "Bearer errado"}).status_code == 401
        ok = client.get("/metrics", headers={"Authorization": "Bearer s3cret"})
    assert ok.status_code == 200
    assert "ocean_http_requests_total" in ok.text
