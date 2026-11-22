from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Literal

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

logger = structlog.get_logger()
BRASILIA = timezone(timedelta(hours=-3))
HISTORY_TAIL = 4


class RefinedQuestion(BaseModel):
    intent: str = Field(description="Intenção marítima curta e normalizada")
    route: Literal["simple", "live_data", "knowledge", "complex"] = Field(
        default="live_data",
        description="Rota: simple, live_data, knowledge ou complex",
    )
    location: str | None = Field(default=None, description="Local brasileiro mencionado ou inferido")
    date: str | None = Field(default=None, description="Data no formato AAAA-MM-DD")
    metric: str | None = Field(default=None, description="Informação solicitada, como maré ou ondas")
    refined_query: str = Field(description="Pergunta completa pronta para execução pelas ferramentas")
    needs_clarification: bool = False
    clarification_question: str = ""


def _render_history(history: Sequence[BaseMessage]) -> str:
    tail = list(history)[-HISTORY_TAIL:]
    if not tail:
        return "(sem histórico)"
    return "\n".join(f"{message.type}: {str(message.content)[:300]}" for message in tail)


async def refine_question(
    llm: BaseChatModel,
    message: str,
    history: Sequence[BaseMessage] = (),
    config: RunnableConfig | None = None,
) -> RefinedQuestion:
    today = datetime.now(BRASILIA).strftime("%Y-%m-%d")
    prompt = f"""Você refina perguntas para um agente marítimo brasileiro.

Data de hoje em Brasília: {today}.

Converta perguntas vagas em uma consulta objetiva. Preserve o significado original.
Use o histórico apenas para resolver referências como "lá", "amanhã" ou "e em Santos".
Não invente local ou data. Se faltar uma informação essencial, marque needs_clarification=true
e faça uma pergunta curta em clarification_question.

Classifique a rota:
- simple: resposta curta sem comparação nem dado atual;
- live_data: condição atual ou previsão de mar, maré ou defeso;
- knowledge: conceito ou explicação encontrada no RAG;
- complex: múltiplos locais, datas, métricas ou ferramentas, ou comparação.

Retorne somente a estrutura solicitada."""

    try:
        structured = llm.with_structured_output(RefinedQuestion)
        result = await structured.ainvoke(
            [
                SystemMessage(content=prompt),
                HumanMessage(
                    content=f"Histórico recente:\n{_render_history(history)}\n\n"
                    f"Pergunta do usuário:\n{message}"
                ),
            ],
            config=config,
        )
        if isinstance(result, RefinedQuestion):
            return result
        return RefinedQuestion.model_validate(result)
    except Exception:
        logger.warning("question.refiner_failed", stage="question_refiner", exc_info=True)
        return RefinedQuestion(
            intent="maritime",
            refined_query=message,
        )
