from collections.abc import Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
import structlog

from src.agent.prompts.system import (
    REFUSAL_NO_SOURCES,
    REFUSAL_OUT_OF_SCOPE,
    SYSTEM_PROMPT,
)
from src.agent.scope import classify_scope
from src.core.config import Settings
from src.llm.provider import create_llm
from src.mcp.client import MCPClient
from src.mcp.tools import mcp_tools_to_langchain
from src.security.guardrails import validate_user_message


class OceanAgent:
    def __init__(self, settings: Settings, mcp_client: MCPClient | None = None) -> None:
        self.settings = settings
        self.mcp_client = mcp_client or MCPClient(settings)
        self.logger = structlog.get_logger()

    async def _load_allowed_tools(self) -> list:
        """Descobre as ferramentas do MCP e mantém só as liberadas em ALLOWED_TOOLS.

        Ferramentas de escrita (ex.: set_speed) ficam de fora por padrão: o chat público
        não deve poder alterar o estado da frota.
        """
        try:
            discovered = await self.mcp_client.list_tools()
        except Exception:
            self.logger.warning("mcp.discovery_failed", stage="mcp_tool_discovery")
            return []

        allowed = self.settings.allowed_tool_names
        selected = [t for t in discovered if str(t.get("name", "")) in allowed]
        self.logger.info(
            "mcp.tools_discovered",
            stage="mcp_tool_discovery",
            discovered=len(discovered),
            allowed=len(selected),
        )
        return mcp_tools_to_langchain(selected, self.mcp_client)

    async def run(
        self,
        message: str,
        history: Sequence[BaseMessage] = (),
    ) -> str:
        clean_message = validate_user_message(message)
        llm = create_llm(self.settings)

        # Camada 1: portão de escopo, antes de qualquer ferramenta ou resposta.
        decision = await classify_scope(llm, clean_message, history)
        if not decision.in_scope:
            self.logger.info("scope.refused", stage="scope_gate", reason=decision.reason)
            return REFUSAL_OUT_OF_SCOPE

        # Camada 2: só ferramentas permitidas. Sem fontes, não responde de memória.
        tools = await self._load_allowed_tools()
        if not tools:
            return REFUSAL_NO_SOURCES

        # Camada 3: prompt restritivo com regra de fundamentação.
        graph = create_react_agent(llm, tools=tools, prompt=SYSTEM_PROMPT)
        self.logger.info("llm.execution_started", stage="llm_execution")
        messages = [*history, HumanMessage(content=clean_message)]
        result = await graph.ainvoke({"messages": messages})

        messages = result.get("messages", [])
        if messages:
            final = messages[-1]
            if isinstance(final, AIMessage):
                return str(final.content)
        raise RuntimeError("agent did not produce a response")
