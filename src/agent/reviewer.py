import re

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from src.core.sources import SourceRef

logger = structlog.get_logger()

UNSAFE_RESPONSE_PATTERNS = (
    re.compile(r"(?i)\b(?:é seguro|pode sair|pode navegar|bom ponto de pesca)\b"),
)


class ResponseReview(BaseModel):
    approved: bool
    reason: str = ""
    corrected_answer: str = ""
    issues: list[str] = Field(default_factory=list)


def deterministic_response_review(text: str) -> list[str]:
    issues: list[str] = []
    if not text or not text.strip():
        issues.append("A resposta está vazia.")
    if len(text) > 12_000:
        issues.append("A resposta excede o limite seguro.")
    if any(pattern.search(text) for pattern in UNSAFE_RESPONSE_PATTERNS):
        issues.append("A resposta faz afirmação insegura sobre navegação ou pesca.")
    return issues


async def validate_complex_response(
    llm: BaseChatModel,
    question: str,
    answer: str,
    sources: list[SourceRef],
    config: RunnableConfig | None = None,
) -> ResponseReview:
    prompt = """Você é um revisor factual para um assistente marítimo brasileiro.

A resposta será aprovada somente se:
- responde à pergunta original e não introduz fatos fora das fontes;
- usa corretamente local, data e hora;
- preserva status stale, partial ou unavailable quando presente;
- menciona limitações relevantes;
- não afirma que navegar ou pescar é seguro;
- não inventa fonte, número ou recomendação.

Não tenha preferência estilística. Em caso de dúvida, reprove.
Se puder corrigir sem inventar, forneça corrected_answer.
Caso contrário, deixe corrected_answer vazio.
Retorne somente a estrutura solicitada."""

    source_context = [
        {
            "tool": source.tool,
            "name": source.name,
            "status": source.status,
            "freshness": source.freshness,
            "data_timestamp": source.data_timestamp,
            "limitations": source.limitations,
        }
        for source in sources
    ]
    try:
        structured = llm.with_structured_output(ResponseReview)
        result = await structured.ainvoke(
            [
                SystemMessage(content=prompt),
                HumanMessage(
                    content=(
                        f"Pergunta:\n{question}\n\n"
                        f"Resposta:\n{answer}\n\n"
                        f"Fontes consultadas:\n{source_context}"
                    )
                ),
            ],
            config=config,
        )
        if isinstance(result, ResponseReview):
            return result
        return ResponseReview.model_validate(result)
    except Exception:
        logger.warning("response.validator_failed", stage="response_validator", exc_info=True)
        return ResponseReview(
            approved=True,
            reason="validador_indisponivel",
        )
