from unittest.mock import AsyncMock, MagicMock, patch

from src.agent.graph import OceanAgent
from src.agent.prompts.system import REFUSAL_NO_SOURCES, REFUSAL_OUT_OF_SCOPE
from src.agent.scope import ScopeDecision
from src.core.config import Settings


def _settings() -> Settings:
    return Settings(groq_api_key="test", allowed_tools="buscar_conhecimento")


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
        answer = await agent.run("me dá uma receita de bolo")
    assert answer == REFUSAL_OUT_OF_SCOPE
    client.list_tools.assert_not_awaited()


async def test_no_allowed_tools_means_no_answer_from_memory():
    tools = [{"name": "set_speed", "description": "x", "inputSchema": {}}]
    agent = OceanAgent(_settings(), _mcp(tools))
    with patch("src.agent.graph.create_llm"), patch(
        "src.agent.graph.classify_scope",
        AsyncMock(return_value=ScopeDecision(in_scope=True)),
    ):
        answer = await agent.run("qual a maré em Santos?")
    assert answer == REFUSAL_NO_SOURCES


async def test_write_tools_are_filtered_out():
    tools = [
        {"name": "set_speed", "description": "x", "inputSchema": {}},
        {"name": "buscar_conhecimento", "description": "x", "inputSchema": {}},
    ]
    agent = OceanAgent(_settings(), _mcp(tools))
    loaded = await agent._load_allowed_tools()
    assert [t.name for t in loaded] == ["buscar_conhecimento"]
