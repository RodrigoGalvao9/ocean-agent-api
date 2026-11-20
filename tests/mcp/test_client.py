from src.core.config import Settings
from src.mcp.client import MCPClient


def test_mcp_headers_only_include_auth_when_configured():
    client = MCPClient(Settings(mcp_auth_token="secret"))
    assert client._headers()["Authorization"] == "Bearer " + "secret"
    assert MCPClient(Settings())._headers() == {}


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
