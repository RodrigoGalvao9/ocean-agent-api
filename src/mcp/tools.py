from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import create_model
import structlog

from src.mcp.client import MCPClient
from src.security.guardrails import validate_tool_invocation


def _argument_model(name: str, input_schema: dict[str, Any]) -> type:
    properties = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))
    fields = {}
    for field_name, schema in properties.items():
        field_type = str
        if schema.get("type") == "integer":
            field_type = int
        elif schema.get("type") == "number":
            field_type = float
        elif schema.get("type") == "boolean":
            field_type = bool
        elif schema.get("type") == "array":
            field_type = list
        elif schema.get("type") == "object":
            field_type = dict
        fields[field_name] = (field_type, ... if field_name in required else None)
    return create_model(f"{name}Arguments", **fields)


def mcp_tools_to_langchain(tools: list[dict[str, Any]], client: MCPClient) -> list[StructuredTool]:
    logger = structlog.get_logger()
    adapters: list[StructuredTool] = []
    for tool in tools:
        name = str(tool.get("name", ""))
        description = str(tool.get("description") or "MCP tool")
        input_schema = tool.get("inputSchema") or tool.get("input_schema") or {}

        def make_invoker(tool_name: str):
            async def invoke_tool(**kwargs: Any) -> Any:
                validate_tool_invocation(tool_name, kwargs)
                logger.info("mcp.tool_invoked", stage="mcp_tool_invoked", tool_name=tool_name)
                return await client.invoke_tool(tool_name, kwargs)
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
