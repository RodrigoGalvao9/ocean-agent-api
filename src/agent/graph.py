from collections.abc import Sequence
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
import structlog

from src.agent.prompts.system import (
    REFUSAL_NO_SOURCES,
    REFUSAL_OUT_OF_SCOPE,
    build_system_prompt,
)
from src.agent.scope import classify_scope
from src.core.config import Settings
from src.core.sources import SourceRecorder, SourceRef
from src.llm.provider import create_llm
from src.mcp.client import MCPClient
from src.mcp.tools import mcp_tools_to_langchain
from src.observability.metrics import CHAT_OUTCOMES, SCOPE_DECISIONS
from src.observability.tracing import get_callbacks, record_score
from src.security.guardrails import validate_user_message


@dataclass
class AgentResult:
    """Resposta do agente: o texto e as fontes consultadas (proveniência)."""

    text: str
    sources: list[SourceRef] = field(default_factory=list)


class OceanAgent:
    def __init__(self, settings: Settings, mcp_client: MCPClient | None = None) -> None:
        self.settings = settings
        self.mcp_client = mcp_client or MCPClient(settings)
        self.logger = structlog.get_logger()

    async def _load_allowed_tools(self, recorder: SourceRecorder | None = None) -> list:
        """Descobre as ferramentas do MCP e mantém só as liberadas em ALLOWED_TOOLS.

        Só ferramentas de leitura devem estar na lista: o chat público não pode alterar
        estado. As fontes de cada chamada são acumuladas em `recorder`.
        """
        try:
            discovered = await self.mcp_client.list_tools()
        except Exception as exc:
            self.logger.warning(
                "mcp.discovery_failed",
                stage="mcp_tool_discovery",
                error_type=type(exc).__name__,
                error=str(exc)[:300],
            )
            return []

        allowed = self.settings.allowed_tool_names
        selected = [t for t in discovered if str(t.get("name", "")) in allowed]
        discovered_names = [str(t.get("name", "")) for t in discovered]
        self.logger.info(
            "mcp.tools_discovered",
            stage="mcp_tool_discovery",
            discovered=len(discovered),
            allowed=len(selected),
            discovered_names=discovered_names,
            allowed_names=sorted(allowed),
        )
        return mcp_tools_to_langchain(
            selected,
            self.mcp_client,
            recorder=recorder,
            max_output_chars=self.settings.max_tool_output_chars,
        )

    async def run(
        self,
        message: str,
        history: Sequence[BaseMessage] = (),
    ) -> AgentResult:
        clean_message = validate_user_message(message)
        llm = create_llm(self.settings)
        # Só as últimas mensagens vão ao LLM: controla custo e o efeito de históricos longos.
        history = list(history)[-self.settings.max_history_messages :]
        config = {"callbacks": get_callbacks()}

        # Camada 1: portão de escopo, antes de qualquer ferramenta ou resposta.
        decision = await classify_scope(
            llm, clean_message, history, config={**config, "run_name": "scope-gate"}
        )
        if decision.reason == "classifier_unavailable":
            SCOPE_DECISIONS.labels(decision="classifier_error").inc()
        else:
            SCOPE_DECISIONS.labels(decision="in_scope" if decision.in_scope else "out_of_scope").inc()
            record_score("scope_in_scope", 1.0 if decision.in_scope else 0.0, decision.reason)
        if not decision.in_scope:
            self.logger.info("scope.refused", stage="scope_gate", reason=decision.reason)
            CHAT_OUTCOMES.labels(outcome="refused_scope").inc()
            return AgentResult(REFUSAL_OUT_OF_SCOPE)

        # Camada 2: só ferramentas permitidas. Sem fontes, não responde de memória.
        recorder = SourceRecorder()
        tools = await self._load_allowed_tools(recorder)
        if not tools:
            CHAT_OUTCOMES.labels(outcome="refused_no_sources").inc()
            return AgentResult(REFUSAL_NO_SOURCES)

        # Camada 3: prompt restritivo com regra de fundamentação (e a data de hoje).
        graph = create_react_agent(llm, tools=tools, prompt=build_system_prompt())
        self.logger.info("llm.execution_started", stage="llm_execution")
        messages = [*history, HumanMessage(content=clean_message)]
        result = await graph.ainvoke(
            {"messages": messages}, config={**config, "run_name": "ocean-agent"}
        )

        messages = result.get("messages", [])
        if messages:
            final = messages[-1]
            if isinstance(final, AIMessage):
                CHAT_OUTCOMES.labels(outcome="answered").inc()
                # A atribuição exigida pelas licenças das fontes é anexada pelo código.
                text = str(final.content) + recorder.attribution_footer()
                return AgentResult(text, recorder.sources)
        raise RuntimeError("agent did not produce a response")
