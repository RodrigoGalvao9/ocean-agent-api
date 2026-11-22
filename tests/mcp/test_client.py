from src.core.config import Settings
from src.mcp.client import MCPClient


def test_mcp_headers_only_include_auth_when_configured():
    client = MCPClient(Settings(mcp_auth_token="secret"))
    assert client._headers()["Authorization"] == "Bearer " + "secret"
    assert MCPClient(Settings())._headers() == {}


def test_production_mcp_requires_https_and_authentication():
    with pytest.raises(ConfigurationError, match="HTTPS"):
        MCPClient(Settings(environment="production", mcp_server_url="http://mcp.test/mcp"))
    with pytest.raises(ConfigurationError, match="MCP_AUTH_TOKEN"):
        MCPClient(Settings(environment="production", mcp_server_url="https://mcp.test/mcp"))


async def test_session_sends_bearer_header_and_accepts_two_stream_tuple():
    """Regressão: SDK novo não aceita headers=, exige http_client e devolve 2 streams."""
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock, MagicMock, patch

    from src.core.config import Settings
    from src.mcp.client import MCPClient

    captured = {}

    @asynccontextmanager
    async def fake_transport(url, *, http_client=None, **_):
        captured["url"] = url
        captured["auth"] = http_client.headers.get("authorization")
        yield (MagicMock(), MagicMock())  # 2 valores, como no SDK atual

    session = MagicMock()
    session.initialize = AsyncMock()
    session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=False)

    settings = Settings(mcp_server_url="http://mcp.test/mcp", mcp_auth_token="tok")
    with patch("mcp.client.streamable_http.streamable_http_client", fake_transport), patch(
        "mcp.ClientSession", return_value=session_cm
    ):
        assert await MCPClient(settings).list_tools() == []

    assert captured == {"url": "http://mcp.test/mcp", "auth": "Bearer tok"}


# ---------------------------------------------------------------------------
# Resultado normalizado, cache da lista de ferramentas, partida a frio e nova tentativa
# ---------------------------------------------------------------------------
import asyncio  # noqa: E402
import time  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402

import pytest  # noqa: E402
from mcp.types import CallToolResult, TextContent  # noqa: E402

from src.core.exceptions import MCPError  # noqa: E402
from src.core.exceptions import ConfigurationError  # noqa: E402
from src.mcp import client as client_module  # noqa: E402
from src.mcp.client import normalize_call_result  # noqa: E402


def _text(value: str) -> TextContent:
    return TextContent(type="text", text=value)


def test_normalize_prefers_structured_content():
    result = CallToolResult(
        content=[_text('{"duplicado": true}')],
        structuredContent={"status": "ok", "source": "X", "data": {"a": 1}},
    )
    assert normalize_call_result(result) == {"status": "ok", "source": "X", "data": {"a": 1}}


def test_normalize_parses_json_text_and_falls_back_to_plain_text():
    assert normalize_call_result(CallToolResult(content=[_text('{"status":"ok"}')])) == {
        "status": "ok"
    }
    assert normalize_call_result(CallToolResult(content=[_text("texto livre")])) == {
        "text": "texto livre"
    }
    assert normalize_call_result(CallToolResult(content=[_text("[1,2]")])) == {"result": [1, 2]}


def test_normalize_marks_tool_errors_as_unavailable():
    result = CallToolResult(content=[_text("Erro: parâmetro inválido")], isError=True)
    out = normalize_call_result(result)
    assert out["status"] == "unavailable" and "parâmetro inválido" in out["detail"]


def _fake_session_factory(session):
    @asynccontextmanager
    async def fake(self, timeout=None):
        fake.timeouts.append(timeout)
        yield session

    fake.timeouts = []
    return fake


def _session(tools=None):
    session = MagicMock()
    tool = MagicMock()
    tool.model_dump.return_value = {"name": "t", "description": "d", "inputSchema": {}}
    session.list_tools = AsyncMock(return_value=MagicMock(tools=tools or [tool]))
    session.call_tool = AsyncMock(
        return_value=CallToolResult(
            content=[_text("{}")], structuredContent={"status": "ok", "source": "S"}
        )
    )
    return session


async def test_tool_list_is_cached_until_ttl_expires():
    session = _session()
    fake = _fake_session_factory(session)
    settings = Settings(mcp_tools_cache_ttl_seconds=300)
    with patch.object(MCPClient, "_session", fake):
        first = await MCPClient(settings).list_tools()
        second = await MCPClient(settings).list_tools()  # outro cliente: o cache é compartilhado
        assert first == second and session.list_tools.await_count == 1

        client_module._state.tools_at -= 301  # expira
        await MCPClient(settings).list_tools()
        assert session.list_tools.await_count == 2

        await MCPClient(settings).list_tools(use_cache=False)
        assert session.list_tools.await_count == 3


async def test_empty_tool_list_is_not_cached():
    session = MagicMock()
    session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
    with patch.object(MCPClient, "_session", _fake_session_factory(session)):
        assert await MCPClient(Settings()).list_tools() == []
        await MCPClient(Settings()).list_tools()
    assert session.list_tools.await_count == 2


async def test_cold_server_gets_the_long_timeout_and_warm_server_the_short_one():
    session = _session()
    fake = _fake_session_factory(session)
    settings = Settings(request_timeout_seconds=10, mcp_cold_start_timeout_seconds=55)
    with patch.object(MCPClient, "_session", fake):
        await MCPClient(settings).invoke_tool("t", {})  # nunca respondeu: pode estar dormindo
        await MCPClient(settings).invoke_tool("t", {})  # acabou de responder: acordado
        client_module._state.last_ok -= settings.mcp_warm_window_seconds + 1  # passou a janela
        await MCPClient(settings).invoke_tool("t", {})
    assert fake.timeouts == [55, 10, 55]


async def test_connection_failure_is_retried_once_then_succeeds():
    session = _session()
    calls = {"n": 0}

    @asynccontextmanager
    async def flaky(self, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("recusada")
        yield session

    with patch.object(MCPClient, "_session", flaky), patch.object(
        client_module, "_RETRY_DELAY_SECONDS", 0
    ):
        out = await MCPClient(Settings()).invoke_tool("t", {"a": 1})
    assert out["source"] == "S" and calls["n"] == 2


async def test_timeout_is_not_retried_and_raises_mcp_error():
    calls = {"n": 0}

    @asynccontextmanager
    async def slow(self, timeout=None):
        calls["n"] += 1
        await asyncio.sleep(1)
        yield MagicMock()

    settings = Settings(request_timeout_seconds=0.05, mcp_cold_start_timeout_seconds=0.05)
    with patch.object(MCPClient, "_session", slow), pytest.raises(MCPError):
        await MCPClient(settings).invoke_tool("t", {})
    assert calls["n"] == 1


async def test_two_connection_failures_raise_mcp_error():
    @asynccontextmanager
    async def down(self, timeout=None):
        raise ConnectionError("fora do ar")
        yield  # pragma: no cover

    with patch.object(MCPClient, "_session", down), patch.object(
        client_module, "_RETRY_DELAY_SECONDS", 0
    ), pytest.raises(MCPError):
        await MCPClient(Settings()).list_tools()
    assert client_module._state.last_ok is None


def test_success_marks_the_server_as_warm():
    assert client_module._state.last_ok is None
    session = _session()
    with patch.object(MCPClient, "_session", _fake_session_factory(session)):
        asyncio.run(MCPClient(Settings()).invoke_tool("t", {}))
    assert time.monotonic() - client_module._state.last_ok < 5
