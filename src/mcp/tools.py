import json
import time
from typing import Any, Literal

import structlog
from langchain_core.tools import StructuredTool
from pydantic import Field, create_model

from src.core.exceptions import MCPError
from src.core.sources import SourceRecorder
from src.mcp.client import MCPClient
from src.observability.metrics import MCP_TOOL_CALLS, MCP_TOOL_LATENCY
from src.security.guardrails import validate_tool_invocation

_JSON_TYPES: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}
_KNOWN_STATUS = {"ok", "partial", "stale", "unavailable"}
DEFAULT_MAX_OUTPUT_CHARS = 12_000

UNAVAILABLE_PAYLOAD = {
    "status": "unavailable",
    "error": "tool_unavailable",
    "limitations": ["A fonte de dados está temporariamente indisponível."],
}


def _python_type(schema: dict[str, Any]) -> Any:
    """Converte um trecho de JSON Schema no tipo Python correspondente."""
    if schema.get("enum"):
        return Literal[tuple(schema["enum"])]
    options = schema.get("anyOf") or schema.get("oneOf")
    if options:  # parâmetro opcional: anyOf [tipo, null]
        non_null = [o for o in options if o.get("type") != "null"]
        return _python_type(non_null[0]) if len(non_null) == 1 else Any
    return _JSON_TYPES.get(schema.get("type"), str)


def _argument_model(name: str, input_schema: dict[str, Any]) -> type:
    """Cria o modelo de argumentos da ferramenta, preservando tipo, enum, padrão e descrição.

    A descrição de cada parâmetro é o que o modelo lê para saber o que preencher.
    """
    properties = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))
    fields: dict[str, Any] = {}
    for field_name, schema in properties.items():
        field_type = _python_type(schema)
        description = schema.get("description") or schema.get("title")
        if field_name in required:
            fields[field_name] = (field_type, Field(..., description=description))
        elif schema.get("default") is not None:
            fields[field_name] = (field_type, Field(schema["default"], description=description))
        else:
            fields[field_name] = (field_type | None, Field(None, description=description))
    return create_model(f"{name}Arguments", **fields)


def render_tool_output(payload: dict[str, Any], max_chars: int = DEFAULT_MAX_OUTPUT_CHARS) -> str:
    """Texto enviado ao modelo. Mantém sempre status, fonte, datas e limitações; se for
    preciso cortar, corta só o campo `data` (que vem por último)."""
    if "data" not in payload:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))[:max_chars]

    head = {k: v for k, v in payload.items() if k != "data"}
    data = payload["data"]
    full = json.dumps({**head, "data": data}, ensure_ascii=False, separators=(",", ":"))
    if len(full) <= max_chars:
        return full

    head_text = json.dumps(head, ensure_ascii=False, separators=(",", ":"))
    budget = max(max_chars - len(head_text) - 60, 200)
    data_text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))[:budget]
    return json.dumps(
        {**head, "truncated": True, "data": data_text + "…"}, ensure_ascii=False, separators=(",", ":")
    )


def mcp_tools_to_langchain(
    tools: list[dict[str, Any]],
    client: MCPClient,
    recorder: SourceRecorder | None = None,
    max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
) -> list[StructuredTool]:
    logger = structlog.get_logger()
    adapters: list[StructuredTool] = []
    for tool in tools:
        name = str(tool.get("name", ""))
        description = str(tool.get("description") or "MCP tool")
        input_schema = tool.get("inputSchema") or tool.get("input_schema") or {}

        def make_invoker(tool_name: str):
            async def invoke_tool(**kwargs: Any) -> str:
                # Parâmetros opcionais que o modelo deixou nulos não vão ao servidor: lá valem
                # os padrões da ferramenta.
                arguments = {k: v for k, v in kwargs.items() if v is not None}
                validate_tool_invocation(tool_name, arguments)
                logger.info("mcp.tool_invoked", stage="mcp_tool_invoked", tool_name=tool_name)

                started = time.perf_counter()
                try:
                    payload = await client.invoke_tool(tool_name, arguments)
                    status = payload.get("status")
                    label = status if status in _KNOWN_STATUS else "ok"
                except MCPError:
                    # Falha de infraestrutura vira resposta de ferramenta: o modelo explica a
                    # indisponibilidade em vez de a requisição inteira falhar com erro 502.
                    payload = {**UNAVAILABLE_PAYLOAD, "tool": tool_name}
                    label = "error"
                MCP_TOOL_CALLS.labels(tool=tool_name, status=label).inc()
                MCP_TOOL_LATENCY.labels(tool=tool_name).observe(time.perf_counter() - started)

                if recorder is not None:
                    recorder.record(tool_name, payload)
                return render_tool_output(payload, max_output_chars)

            return invoke_tool

        adapters.append(
            StructuredTool(
                name=name,
                description=description,
                args_schema=_argument_model(name, input_schema),
                coroutine=make_invoker(name),
            )
        )
    return adapters
