import asyncio
from collections.abc import Mapping
from typing import Any

from src.core.config import Settings
from src.core.exceptions import MCPError


class MCPClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _headers(self) -> dict[str, str]:
        if not self.settings.mcp_auth_token:
            return {}
        return {"Authorization": "Bearer " + self.settings.mcp_auth_token}

    async def list_tools(self) -> list[dict[str, Any]]:
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamable_http_client

            async with asyncio.timeout(self.settings.request_timeout_seconds):
                async with streamable_http_client(
                    self.settings.mcp_server_url,
                    headers=self._headers(),
                    timeout=self.settings.request_timeout_seconds,
                ) as (read_stream, write_stream, _):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        result = await session.list_tools()
            return [tool.model_dump(by_alias=True, exclude_none=True) for tool in result.tools]
        except Exception as exc:
            raise MCPError("unable to connect to or discover MCP tools") from exc

    async def invoke_tool(self, name: str, arguments: Mapping[str, Any]) -> Any:
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamable_http_client

            async with asyncio.timeout(self.settings.request_timeout_seconds):
                async with streamable_http_client(
                    self.settings.mcp_server_url,
                    headers=self._headers(),
                    timeout=self.settings.request_timeout_seconds,
                ) as (read_stream, write_stream, _):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        result = await session.call_tool(name, dict(arguments))
            return result.model_dump(by_alias=True, exclude_none=True)
        except Exception as exc:
            raise MCPError("unable to invoke MCP tool") from exc
