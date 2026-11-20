from collections.abc import Sequence

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel

from src.agent.prompts.system import SCOPE_CLASSIFIER_PROMPT

logger = structlog.get_logger()

HISTORY_TAIL = 4  # últimas mensagens usadas só para entender perguntas de continuação


class ScopeDecision(BaseModel):
    """Resultado da classificação de escopo."""

    in_scope: bool
    reason: str = ""


def _render_history(history: Sequence[BaseMessage]) -> str:
    tail = list(history)[-HISTORY_TAIL:]
    if not tail:
        return "(sem histórico)"
    return "\n".join(f"{m.type}: {str(m.content)[:300]}" for m in tail)


async def classify_scope(
    llm: BaseChatModel,
    message: str,
    history: Sequence[BaseMessage] = (),
) -> ScopeDecision:
    """Decide se a mensagem pertence ao domínio marítimo.

    Se o classificador falhar, segue como dentro do escopo (fail-open): o prompt restritivo,
    o allowlist de ferramentas e a regra de fundamentação continuam protegendo a resposta.
    """
    try:
        structured = llm.with_structured_output(ScopeDecision)
        decision = await structured.ainvoke(
            [
                SystemMessage(content=SCOPE_CLASSIFIER_PROMPT),
                HumanMessage(
                    content=f"Histórico recente:\n{_render_history(history)}\n\n"
                    f"Mensagem do usuário:\n{message}"
                ),
            ]
        )
        if isinstance(decision, ScopeDecision):
            return decision
        return ScopeDecision.model_validate(decision)
    except Exception:
        logger.warning("scope.classifier_failed", stage="scope_gate", exc_info=True)
        return ScopeDecision(in_scope=True, reason="classifier_unavailable")
