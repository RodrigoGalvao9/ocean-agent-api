import json
from typing import get_args
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from src.core.exceptions import MCPError
from src.core.sources import SourceRecorder
from src.mcp.tools import _argument_model, mcp_tools_to_langchain, render_tool_output
from src.observability.metrics import MCP_TOOL_CALLS

SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Pergunta do usuário"},
        "k": {"type": "integer", "default": 4, "description": "Quantidade de trechos"},
        "place": {
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "description": "Lugar, em texto",
        },
        "radius_km": {"anyOf": [{"type": "number"}, {"type": "null"}]},
        "kind": {"type": "string", "enum": ["mercado", "terminal"]},
    },
    "required": ["query"],
}


def test_argument_model_keeps_types_defaults_enums_and_descriptions():
    model = _argument_model("t", SCHEMA)
    fields = model.model_fields

    assert fields["query"].is_required() and fields["query"].description == "Pergunta do usuário"
    assert fields["k"].default == 4 and fields["k"].description == "Quantidade de trechos"
    # Opcionais (anyOf com null) mantêm o tipo real, em vez de virarem texto.
    assert float in get_args(fields["radius_km"].annotation)
    assert str in get_args(fields["place"].annotation)
    assert fields["place"].default is None

    assert model(query="x", kind="mercado").kind == "mercado"
    with pytest.raises(ValidationError):
        model(query="x", kind="shopping")  # enum respeitado
    with pytest.raises(ValidationError):
        model(query="x", k="muitos")  # tipo respeitado


def test_json_schema_shown_to_the_llm_has_the_descriptions():
    schema = _argument_model("t", SCHEMA).model_json_schema()
    assert schema["properties"]["query"]["description"] == "Pergunta do usuário"


def test_render_output_keeps_provenance_and_marks_truncation():
    payload = {
        "status": "ok",
        "source": "Fonte",
        "limitations": ["só maré astronômica"],
        "data": {"results": ["x" * 500] * 100},
    }
    short = render_tool_output(payload, max_chars=100_000)
    assert json.loads(short) == payload

    cut = render_tool_output(payload, max_chars=2_000)
    parsed = json.loads(cut)  # continua sendo JSON válido
    assert len(cut) <= 2_200
    assert parsed["truncated"] is True
    assert parsed["source"] == "Fonte" and parsed["limitations"] == ["só maré astronômica"]


def test_render_output_without_data_field_is_unchanged():
    assert json.loads(render_tool_output({"status": "unavailable"})) == {"status": "unavailable"}


def _adapter(client, recorder=None, **kw):
    tool = {"name": "get_x", "description": "d", "inputSchema": SCHEMA}
    return mcp_tools_to_langchain([tool], client, recorder=recorder, **kw)[0]


async def test_omitted_and_null_optionals_are_not_sent_to_the_server():
    client = MagicMock()
    client.invoke_tool = AsyncMock(return_value={"status": "ok", "source": "S", "data": {}})
    tool = _adapter(client)

    await tool.ainvoke({"query": "o que é preamar?"})
    client.invoke_tool.assert_awaited_with("get_x", {"query": "o que é preamar?"})

    await tool.ainvoke({"query": "q", "place": None, "k": 2})
    client.invoke_tool.assert_awaited_with("get_x", {"query": "q", "k": 2})


async def test_tool_returns_json_text_records_source_and_counts_the_call():
    client = MagicMock()
    client.invoke_tool = AsyncMock(
        return_value={"status": "partial", "source": "S", "retrieved_at": "t", "data": {"a": 1}}
    )
    recorder = SourceRecorder()
    before = MCP_TOOL_CALLS.labels(tool="get_x", status="partial")._value.get()

    out = await _adapter(client, recorder).ainvoke({"query": "q"})

    assert json.loads(out)["data"] == {"a": 1}
    assert [s.name for s in recorder.sources] == ["S"]
    assert MCP_TOOL_CALLS.labels(tool="get_x", status="partial")._value.get() == before + 1


async def test_mcp_failure_becomes_an_unavailable_result_instead_of_raising():
    client = MagicMock()
    client.invoke_tool = AsyncMock(side_effect=MCPError("fora"))
    recorder = SourceRecorder()
    before = MCP_TOOL_CALLS.labels(tool="get_x", status="error")._value.get()

    out = json.loads(await _adapter(client, recorder).ainvoke({"query": "q"}))

    assert out["status"] == "unavailable" and out["tool"] == "get_x" and out["limitations"]
    assert recorder.sources == []
    assert MCP_TOOL_CALLS.labels(tool="get_x", status="error")._value.get() == before + 1


async def test_output_is_capped_by_max_output_chars():
    client = MagicMock()
    client.invoke_tool = AsyncMock(
        return_value={"status": "ok", "source": "S", "data": {"t": "y" * 50_000}}
    )
    out = await _adapter(client, max_output_chars=1_000).ainvoke({"query": "q"})
    assert len(out) <= 1_200 and json.loads(out)["truncated"] is True


async def test_rag_top_k_is_capped_by_configuration():
    client = MagicMock()
    client.invoke_tool = AsyncMock(
        return_value={"status": "ok", "source": "RAG", "data": {"items": []}}
    )
    tool = {
        "name": "search_maritime_knowledge",
        "description": "Busca RAG",
        "inputSchema": SCHEMA,
    }
    adapter = mcp_tools_to_langchain(
        [tool],
        client,
        rag_top_k=5,
    )[0]

    await adapter.ainvoke({"query": "o que é preamar?", "k": 50})

    client.invoke_tool.assert_awaited_with(
        "search_maritime_knowledge",
        {"query": "o que é preamar?", "k": 5},
    )
