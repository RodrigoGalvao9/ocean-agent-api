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
from src.agent.refiner import refine_question
from src.agent.reviewer import (
    deterministic_response_review,
    validate_complex_response,
)
from src.agent.scope import classify_scope
from src.core.config import Settings
from src.core.sources import SourceRecorder, SourceRef
from src.llm.provider import (
    create_llm,
    create_openrouter_refiner,
    create_openrouter_validator,
)
from src.mcp.client import MCPClient
from src.mcp.tools import mcp_tools_to_langchain
from src.observability.metrics import (
    CHAT_OUTCOMES,
    QUESTION_ROUTES,
    RESPONSE_VALIDATIONS,
    SCOPE_DECISIONS,
)
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

        # Camada opcional: refinador estruturado via OpenRouter.
        refined_message = clean_message
        route = "live_data"
        refiner = create_openrouter_refiner(self.settings)
        if refiner is not None:
            refined = await refine_question(
                refiner,
                clean_message,
                history,
                config={**config, "run_name": "question-refiner"},
            )
            if refined.needs_clarification:
                CHAT_OUTCOMES.labels(outcome="needs_clarification").inc()
                question = refined.clarification_question or (
                    "Você pode informar o local ou a data que deseja consultar?"
                )
                return AgentResult(question)
            refined_message = refined.refined_query
            route = refined.route
            self.logger.info(
                "question.refined",
                stage="question_refiner",
                intent=refined.intent,
                route=route,
                location=refined.location,
                date=refined.date,
                metric=refined.metric,
            )
        QUESTION_ROUTES.labels(route=route).inc()

        # Camada 2: só ferramentas permitidas. Sem fontes, não responde de memória.
        recorder = SourceRecorder()
        tools = await self._load_allowed_tools(recorder)
        if not tools:
            CHAT_OUTCOMES.labels(outcome="refused_no_sources").inc()
            return AgentResult(REFUSAL_NO_SOURCES)

        # Camada 3: prompt restritivo com regra de fundamentação (e a data de hoje).
        graph = create_react_agent(llm, tools=tools, prompt=build_system_prompt())
        self.logger.info("llm.execution_started", stage="llm_execution")
        messages = [*history, HumanMessage(content=refined_message)]
        result = await graph.ainvoke(
            {"messages": messages}, config={**config, "run_name": "ocean-agent"}
        )

        messages = result.get("messages", [])
        if messages:
            final = messages[-1]
            if isinstance(final, AIMessage):
                text = str(final.content)
                rejected = False

                deterministic_issues = deterministic_response_review(text)
                if deterministic_issues:
                    RESPONSE_VALIDATIONS.labels(result="deterministic_rejected").inc()
                    rejected = True
                    text = (
                        "Não consegui confirmar esta resposta com segurança com os dados "
                        "disponíveis."
                    )
                elif route == "complex":
                    validator = create_openrouter_validator(self.settings)
                    if validator is not None:
                        review = await validate_complex_response(
                            validator,
                            refined_message,
                            text,
                            recorder.sources,
                            config={**config, "run_name": "response-validator"},
                        )
                        if review.reason == "validador_indisponivel":
                            RESPONSE_VALIDATIONS.labels(result="unavailable").inc()
                        elif review.approved:
                            RESPONSE_VALIDATIONS.labels(result="approved").inc()
                        else:
                            RESPONSE_VALIDATIONS.labels(result="rejected").inc()
                            if review.corrected_answer.strip():
                                text = review.corrected_answer.strip()
                            else:
                                rejected = True
                                text = (
                                    "Não consegui confirmar esta resposta com segurança "
                                    "com os dados disponíveis."
                                )

                # A atribuição exigida pelas licenças das fontes é anexada pelo código.
                text = text + recorder.attribution_footer()
                CHAT_OUTCOMES.labels(
                    outcome="rejected_validation" if rejected else "answered"
                ).inc()
                return AgentResult(text, recorder.sources)
        raise RuntimeError("agent did not produce a response")
