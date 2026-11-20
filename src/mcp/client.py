import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any

import httpx
import structlog

from src.core.config import Settings
from src.core.exceptions import MCPError

logger = structlog.get_logger()


class MCPClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _headers(self) -> dict[str, str]:
        if not self.settings.mcp_auth_token:
            return {}
        return {"Authorization": "Bearer " + self.settings.mcp_auth_token}

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[Any]:
        """Abre uma sessão MCP autenticada.

        O SDK atual (mcp>=1.2x) não aceita headers/timeout em streamable_http_client:
        eles precisam ir em um httpx.AsyncClient passado como http_client.
        """
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        timeout = self.settings.request_timeout_seconds
        async with httpx.AsyncClient(
            headers=self._headers(),
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        ) as http_client:
            async with streamable_http_client(
                self.settings.mcp_server_url,
                http_client=http_client,
            ) as streams:
                # Dependendo da versão do SDK, devolve (read, write) ou (read, write, get_id).
                read_stream, write_stream = streams[0], streams[1]
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    yield session

    async def list_tools(self) -> list[dict[str, Any]]:
        try:
            async with asyncio.timeout(self.settings.request_timeout_seconds):
                async with self._session() as session:
                    result = await session.list_tools()
            return [tool.model_dump(by_alias=True, exclude_none=True) for tool in result.tools]
        except Exception as exc:
            logger.error(
                "mcp.list_tools_failed",
                stage="mcp_tool_discovery",
                url=self.settings.mcp_server_url,
                error_type=type(exc).__name__,
                error=str(exc)[:300],
                exc_info=True,
            )
            raise MCPError("unable to connect to or discover MCP tools") from exc

    async def invoke_tool(self, name: str, arguments: Mapping[str, Any]) -> Any:
        try:
            async with asyncio.timeout(self.settings.request_timeout_seconds):
                async with self._session() as session:
                    result = await session.call_tool(name, dict(arguments))
            return result.model_dump(by_alias=True, exclude_none=True)
        except Exception as exc:
            logger.error(
                "mcp.invoke_failed",
                stage="mcp_tool_invoked",
                tool_name=name,
                error_type=type(exc).__name__,
                error=str(exc)[:300],
                exc_info=True,
            )
            raise MCPError("unable to invoke MCP tool") from exc
