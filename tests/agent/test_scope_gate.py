from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage

from src.agent.graph import OceanAgent
from src.agent.prompts.system import REFUSAL_NO_SOURCES, REFUSAL_OUT_OF_SCOPE
from src.agent.refiner import RefinedQuestion
from src.agent.scope import ScopeDecision
from src.core.config import Settings


def _settings() -> Settings:
    return Settings(
        groq_api_key="test",
        openrouter_api_key="",
        allowed_tools="search_maritime_knowledge",
    )


def _mcp(tools):
    client = MagicMock()
    client.list_tools = AsyncMock(return_value=tools)
    return client


async def test_out_of_scope_is_refused_without_touching_mcp():
    client = _mcp([])
    agent = OceanAgent(_settings(), client)
    with patch("src.agent.graph.create_llm"), patch(
        "src.agent.graph.classify_scope",
        AsyncMock(return_value=ScopeDecision(in_scope=False, reason="receita")),
    ):
        result = await agent.run("me dá uma receita de bolo")
    assert result.text == REFUSAL_OUT_OF_SCOPE
    assert result.sources == []
    client.list_tools.assert_not_awaited()


async def test_ambiguous_question_requests_clarification_before_mcp():
    client = _mcp([])
    agent = OceanAgent(_settings(), client)
    with patch("src.agent.graph.create_llm"), patch(
        "src.agent.graph.create_openrouter_refiner",
        return_value=MagicMock(),
    ), patch(
        "src.agent.graph.refine_question",
        AsyncMock(
            return_value=RefinedQuestion(
                intent="marine_conditions",
                refined_query="",
                needs_clarification=True,
                clarification_question="Em qual local você quer consultar as condições do mar?",
            )
        ),
    ), patch(
        "src.agent.graph.classify_scope",
        AsyncMock(return_value=ScopeDecision(in_scope=True)),
    ):
        result = await agent.run("como está o mar?")
    assert result.text == "Em qual local você quer consultar as condições do mar?"
    assert result.sources == []
    client.list_tools.assert_not_awaited()


async def test_no_allowed_tools_means_no_answer_from_memory():
    tools = [{"name": "set_speed", "description": "x", "inputSchema": {}}]
    agent = OceanAgent(_settings(), _mcp(tools))
    with patch("src.agent.graph.create_llm"), patch(
        "src.agent.graph.classify_scope",
        AsyncMock(return_value=ScopeDecision(in_scope=True)),
    ):
        result = await agent.run("qual a maré em Santos?")
    assert result.text == REFUSAL_NO_SOURCES


async def test_write_tools_are_filtered_out():
    tools = [
        {"name": "set_speed", "description": "x", "inputSchema": {}},
        {"name": "search_maritime_knowledge", "description": "x", "inputSchema": {}},
    ]
    agent = OceanAgent(_settings(), _mcp(tools))
    loaded = await agent._load_allowed_tools()
    assert [t.name for t in loaded] == ["search_maritime_knowledge"]


def test_default_allowlist_has_english_names_and_no_aliases_or_write_tools():
    allowed = Settings().allowed_tool_names
    assert {"search_maritime_knowledge", "get_tide_table", "get_marine_conditions"} <= allowed
    assert "get_tide_table" in allowed
    assert "get_marine_conditions" in allowed
    assert not allowed & {"buscar_conhecimento", "listar_topicos", "set_speed", "get_fleet_state"}


async def test_answer_carries_sources_and_attribution_footer():
    """A fonte vem das chamadas de ferramenta; a atribuição de licença é anexada pelo código."""
    tools = [
        {
            "name": "get_marine_conditions",
            "description": "Condições do mar",
            "inputSchema": {"properties": {"place": {"type": "string"}}, "required": ["place"]},
        }
    ]
    mcp = _mcp(tools)
    mcp.invoke_tool = AsyncMock(
        return_value={
            "status": "ok",
            "source": "Open-Meteo Marine",
            "source_url": "https://open-meteo.com",
            "attribution": "Dados meteorológicos por Open-Meteo.com (CC BY 4.0)",
            "retrieved_at": "2026-11-21T12:00:00Z",
            "freshness": "live",
            "data": {"wave_height_m": 1.2},
        }
    )
    agent = OceanAgent(_settings().model_copy(update={"allowed_tools": "get_marine_conditions"}), mcp)

    class FakeGraph:
        def __init__(self, tools):
            self.tools = tools

        async def ainvoke(self, inputs, config=None):
            # O agente real chamaria a ferramenta; aqui simulamos essa chamada.
            await self.tools[0].ainvoke({"place": "Recife"})
            return {"messages": [AIMessage(content="Ondas de 1,2 m.")]}

    with patch("src.agent.graph.create_llm"), patch(
        "src.agent.graph.classify_scope", AsyncMock(return_value=ScopeDecision(in_scope=True))
    ), patch(
        "src.agent.graph.create_react_agent",
        side_effect=lambda llm, tools, prompt: FakeGraph(tools),
    ):
        result = await agent.run("como está o mar em Recife?")

    assert result.text.startswith("Ondas de 1,2 m.")
    assert result.text.endswith("Atribuição: Dados meteorológicos por Open-Meteo.com (CC BY 4.0)")
    assert [s.name for s in result.sources] == ["Open-Meteo Marine"]
    assert result.sources[0].tool == "get_marine_conditions"
    mcp.invoke_tool.assert_awaited_once_with("get_marine_conditions", {"place": "Recife"})


async def test_tool_outage_becomes_an_answer_not_a_502():
    from src.core.exceptions import MCPError

    tools = [{"name": "get_tide_table", "description": "x", "inputSchema": {}}]
    mcp = _mcp(tools)
    mcp.invoke_tool = AsyncMock(side_effect=MCPError("fora do ar"))
    agent = OceanAgent(_settings().model_copy(update={"allowed_tools": "get_tide_table"}), mcp)

    outputs = []

    class FakeGraph:
        def __init__(self, tools):
            self.tools = tools

        async def ainvoke(self, inputs, config=None):
            outputs.append(await self.tools[0].ainvoke({}))
            return {"messages": [AIMessage(content="A fonte está indisponível.")]}

    with patch("src.agent.graph.create_llm"), patch(
        "src.agent.graph.classify_scope", AsyncMock(return_value=ScopeDecision(in_scope=True))
    ), patch(
        "src.agent.graph.create_react_agent",
        side_effect=lambda llm, tools, prompt: FakeGraph(tools),
    ):
        result = await agent.run("maré em Santos?")

    assert '"status":"unavailable"' in outputs[0]
    assert result.sources == []  # fonte que falhou não aparece como consultada
