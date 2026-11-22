import asyncio
import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.core.config import Settings
from src.core.exceptions import ConfigurationError, MCPError
from src.observability.metrics import MCP_CALLS, MCP_LATENCY

logger = structlog.get_logger()

_RETRY_DELAY_SECONDS = 1.0


@dataclass
class _McpState:
    """Estado compartilhado entre requisições (o cliente é recriado a cada pergunta)."""

    last_ok: float | None = None  # monotonic da última chamada bem-sucedida
    tools: list[dict[str, Any]] | None = None
    tools_at: float = 0.0


_state = _McpState()


def reset_mcp_state() -> None:
    """Zera o estado compartilhado (usado nos testes)."""
    _state.last_ok = None
    _state.tools = None
    _state.tools_at = 0.0


def normalize_call_result(result: Any) -> dict[str, Any]:
    """Transforma o CallToolResult do MCP em um dicionário simples.

    Usa o conteúdo estruturado (o contrato de proveniência) quando existe; senão tenta
    ler o texto como JSON. Isso evita enviar ao modelo o mesmo dado duas vezes.
    """
    blocks = getattr(result, "content", None) or []
    text = " ".join(
        str(getattr(b, "text", "")) for b in blocks if getattr(b, "type", None) == "text"
    ).strip()

    if getattr(result, "isError", False):
        return {"status": "unavailable", "error": "tool_error", "detail": text[:300]}

    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict) and structured:
        return structured

    if text:
        try:
            parsed = json.loads(text)
        except ValueError:
            return {"text": text}
        return parsed if isinstance(parsed, dict) else {"result": parsed}
    return {"text": ""}


class MCPClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        parsed = urlparse(settings.mcp_server_url)
        if settings.environment != "development":
            if parsed.scheme != "https":
                raise ConfigurationError("MCP_SERVER_URL must use HTTPS outside development")
            if not settings.mcp_auth_token:
                raise ConfigurationError("MCP_AUTH_TOKEN is required outside development")

    def _headers(self) -> dict[str, str]:
        if not self.settings.mcp_auth_token:
            return {}
        return {"Authorization": "Bearer " + self.settings.mcp_auth_token}

    def _timeout(self) -> float:
        """Servidor respondeu há pouco: timeout normal. Caso contrário, ele pode estar
        dormindo (plano free): damos tempo para acordar."""
        warm = (
            _state.last_ok is not None
            and (time.monotonic() - _state.last_ok) < self.settings.mcp_warm_window_seconds
        )
        if warm:
            return self.settings.request_timeout_seconds
        return max(
            self.settings.request_timeout_seconds, self.settings.mcp_cold_start_timeout_seconds
        )

    @asynccontextmanager
    async def _session(self, timeout: float | None = None) -> AsyncIterator[Any]:
        """Abre uma sessão MCP autenticada.

        O SDK atual (mcp>=1.2x) não aceita headers/timeout em streamable_http_client:
        eles precisam ir em um httpx.AsyncClient passado como http_client.
        """
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        timeout = timeout or self.settings.request_timeout_seconds
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

    async def _call(
        self,
        operation: str,
        stage: str,
        work: Callable[[Any], Awaitable[Any]],
        **log_context: Any,
    ) -> Any:
        """Executa `work(session)` com timeout adaptativo e UMA nova tentativa.

        Só repete em falha de conexão (rápida). Timeout não é repetido: o servidor já
        teve o tempo de acordar e repetir dobraria a espera do usuário. As ferramentas
        são somente leitura, então repetir é seguro.
        """
        started = time.perf_counter()
        last_exc: BaseException | None = None
        for attempt in (1, 2):
            timeout = self._timeout()
            try:
                async with asyncio.timeout(timeout):
                    async with self._session(timeout) as session:
                        result = await work(session)
            except (TimeoutError, httpx.TimeoutException) as exc:
                last_exc = exc
                break
            except Exception as exc:
                last_exc = exc
                if attempt == 1:
                    logger.warning(
                        "mcp.retrying",
                        stage=stage,
                        operation=operation,
                        error_type=type(exc).__name__,
                        **log_context,
                    )
                    await asyncio.sleep(_RETRY_DELAY_SECONDS)
                    continue
                break
            else:
                _state.last_ok = time.monotonic()
                MCP_CALLS.labels(operation=operation, status="ok").inc()
                MCP_LATENCY.labels(operation=operation).observe(time.perf_counter() - started)
                return result

        MCP_CALLS.labels(operation=operation, status="error").inc()
        MCP_LATENCY.labels(operation=operation).observe(time.perf_counter() - started)
        logger.error(
            f"mcp.{operation}_failed",
            stage=stage,
            url=self.settings.mcp_server_url,
            error_type=type(last_exc).__name__,
            error=str(last_exc)[:300],
            exc_info=last_exc,
            **log_context,
        )
        raise MCPError(f"unable to complete MCP operation: {operation}") from last_exc

    async def list_tools(self, *, use_cache: bool = True) -> list[dict[str, Any]]:
        ttl = self.settings.mcp_tools_cache_ttl_seconds
        if use_cache and _state.tools and (time.monotonic() - _state.tools_at) < ttl:
            return _state.tools

        async def work(session: Any) -> list[dict[str, Any]]:
            result = await session.list_tools()
            return [tool.model_dump(by_alias=True, exclude_none=True) for tool in result.tools]

        tools = await self._call("list_tools", "mcp_tool_discovery", work)
        if tools:  # lista vazia não vale como cache: pode ser um servidor ainda iniciando
            _state.tools, _state.tools_at = tools, time.monotonic()
        return tools

    async def invoke_tool(self, name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        async def work(session: Any) -> dict[str, Any]:
            result = await session.call_tool(name, dict(arguments))
            return normalize_call_result(result)

        return await self._call("invoke_tool", "mcp_tool_invoked", work, tool_name=name)
