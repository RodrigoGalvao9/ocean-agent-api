from src.core.config import Settings
from src.mcp.client import MCPClient


def test_mcp_headers_only_include_auth_when_configured():
    client = MCPClient(Settings(mcp_auth_token="secret"))
    assert client._headers()["Authorization"] == "Bearer " + "secret"
    assert MCPClient(Settings())._headers() == {}
