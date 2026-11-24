import pytest

from src.core.config import Settings, validate_runtime_settings

SECURE = {
    "environment": "production",
    "conversation_session_secret": "s" * 32,
    "mcp_auth_token": "token",
    "mcp_server_url": "https://mcp.test/mcp",
}


def test_default_environment_is_production(monkeypatch):
    # O conftest define ENVIRONMENT=development; aqui queremos o padrão do código.
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    assert Settings(_env_file=None).environment == "production"


def test_production_requires_session_secret():
    values = {**SECURE, "conversation_session_secret": ""}
    with pytest.raises(RuntimeError, match="CONVERSATION_SESSION_SECRET"):
        validate_runtime_settings(Settings(_env_file=None, **values))


def test_production_requires_mcp_token():
    values = {**SECURE, "mcp_auth_token": ""}
    with pytest.raises(RuntimeError, match="MCP_AUTH_TOKEN"):
        validate_runtime_settings(Settings(_env_file=None, **values))


def test_production_requires_https_mcp_url():
    values = {**SECURE, "mcp_server_url": "http://mcp.test/mcp"}
    with pytest.raises(RuntimeError, match="HTTPS"):
        validate_runtime_settings(Settings(_env_file=None, **values))


def test_production_with_secure_settings_passes():
    validate_runtime_settings(Settings(_env_file=None, **SECURE))


def test_development_allows_local_unauthenticated_mcp():
    validate_runtime_settings(Settings(_env_file=None, environment="development"))
