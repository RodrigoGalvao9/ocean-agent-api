from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage

from src.agent.graph import INSUFFICIENT_EVIDENCE_RESPONSE, OceanAgent
from src.core.config import Settings
from src.core.exceptions import RetrievalError


RETRIEVAL_TOOL = {
    "name": "buscar_conhecimento",
    "description": "Busca trechos na base de conhecimento marítimo",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "k": {"type": "integer"},
        },
        "required": ["query"],
    },
}


class FakeMCP:
    def __init__(self, result=None, tools=None, discovery_error=None):
        self.result = result
        self.tools = tools if tools is not None else [RETRIEVAL_TOOL]
        self.discovery_error = discovery_error
        self.invocations = []

    async def list_tools(self):
        if self.discovery_error:
            raise self.discovery_error
        return self.tools

    async def invoke_tool(self, name, arguments):
        self.invocations.append((name, arguments))
        return self.result


class FakeLLM:
    def __init__(self, response="Grounded answer"):
        self.response = response
        self.messages = None

    async def ainvoke(self, messages):
        self.messages = messages
        return AIMessage(content=self.response)


@pytest.mark.asyncio
async def test_fact_question_must_retrieve_before_answering():
    mcp = FakeMCP({"resultados": [{"id": "KB-001", "titulo": "Rules", "texto": "12 knots"}]})
    llm = FakeLLM("The speed limit is 12 knots.")
    with patch("src.agent.graph.create_llm", return_value=llm):
        result = await OceanAgent(Settings(groq_api_key="test"), mcp).run_with_sources(
            "What is the speed limit?"
        )

    assert mcp.invocations == [
        ("buscar_conhecimento", {"query": "What is the speed limit?", "k": 4})
    ]
    assert result.response == "The speed limit is 12 knots."
    assert result.sources[0]["id"] == "KB-001"


@pytest.mark.asyncio
async def test_empty_retrieval_never_answers_from_pretrained_knowledge():
    mcp = FakeMCP({"resultados": []})
    with patch("src.agent.graph.create_llm") as create_llm:
        result = await OceanAgent(Settings(groq_api_key="test"), mcp).run_with_sources(
            "What is the capital of France?"
        )

    create_llm.assert_not_called()
    assert result.response == INSUFFICIENT_EVIDENCE_RESPONSE
    assert result.sources == []


@pytest.mark.asyncio
async def test_mcp_unavailability_is_not_an_llm_fallback():
    mcp = FakeMCP(discovery_error=RuntimeError("offline"))
    with patch("src.agent.graph.create_llm") as create_llm:
        with pytest.raises(RetrievalError, match="unavailable"):
            await OceanAgent(Settings(groq_api_key="test"), mcp).run_with_sources("Question")

    create_llm.assert_not_called()


@pytest.mark.asyncio
async def test_retrieved_context_is_explicitly_passed_to_llm():
    mcp = FakeMCP(
        {
            "resultados": [
                {
                    "id": "KB-009",
                    "titulo": "Storm speed",
                    "texto": "The limit is 12 knots.",
                    "score": 0.91,
                }
            ]
        }
    )
    llm = FakeLLM()
    with patch("src.agent.graph.create_llm", return_value=llm):
        await OceanAgent(Settings(groq_api_key="test"), mcp).run_with_sources("Speed?")

    prompt = "\n".join(str(message.content) for message in llm.messages)
    assert "<retrieved_context>" in prompt
    assert "The limit is 12 knots." in prompt
    assert "KB-009" in prompt


@pytest.mark.asyncio
async def test_unsupported_llm_claim_is_replaced_with_insufficient_evidence():
    mcp = FakeMCP({"resultados": [{"id": "KB-1", "titulo": "Rules", "texto": "Storm limit is 12 knots."}]})
    llm = FakeLLM("The capital of France is Paris.")
    with patch("src.agent.graph.create_llm", return_value=llm):
        result = await OceanAgent(Settings(groq_api_key="test"), mcp).run_with_sources("Question")

    assert result.response == INSUFFICIENT_EVIDENCE_RESPONSE
    assert result.sources == []


@pytest.mark.asyncio
async def test_missing_retrieval_tool_is_observable():
    mcp = FakeMCP(tools=[{"name": "get_fleet_state", "inputSchema": {}}])
    with pytest.raises(RetrievalError, match="buscar_conhecimento"):
        await OceanAgent(Settings(groq_api_key="test"), mcp).run_with_sources("Question")
