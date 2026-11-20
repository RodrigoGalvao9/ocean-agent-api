"""Langfuse (tracing de LLM). Tudo vira no-op sem as chaves, então é seguro em dev e testes."""

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from typing import Any

import structlog

from src.core.config import Settings

logger = structlog.get_logger()

_enabled = False


def init_tracing(settings: Settings) -> bool:
    """Inicializa o cliente global do Langfuse. Retorna True se o tracing ficou ligado."""
    global _enabled
    if not settings.langfuse_enabled:
        _enabled = False
        logger.info("tracing.disabled", stage="startup", reason="missing_langfuse_keys")
        return False
    try:
        from langfuse import Langfuse

        Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
            environment=settings.environment,
            sample_rate=settings.langfuse_sample_rate,
        )
        _enabled = True
        logger.info("tracing.enabled", stage="startup", host=settings.langfuse_host)
    except Exception:
        _enabled = False
        logger.warning("tracing.init_failed", stage="startup", exc_info=True)
    return _enabled


def tracing_enabled() -> bool:
    return _enabled


def shutdown_tracing() -> None:
    """Envia os traces pendentes antes de o processo encerrar."""
    if not _enabled:
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception:
        logger.warning("tracing.flush_failed", stage="shutdown", exc_info=True)


def get_callbacks() -> list[Any]:
    """Callbacks do LangChain/LangGraph para anexar ao `config` de cada execução."""
    if not _enabled:
        return []
    try:
        from langfuse.langchain import CallbackHandler

        return [CallbackHandler()]
    except Exception:
        logger.warning("tracing.handler_failed", stage="tracing", exc_info=True)
        return []


class _RequestTrace:
    """Pequena fachada para atualizar o trace atual sem espalhar try/except pelo código."""

    def __init__(self, span: Any | None) -> None:
        self._span = span

    def set_output(self, output: str) -> None:
        if self._span is None:
            return
        try:
            self._span.update(output=output)
        except Exception:
            logger.warning("tracing.update_failed", stage="tracing", exc_info=True)


@contextmanager
def trace_request(
    *,
    name: str,
    session_id: str | None,
    user_id: str | None,
    input_text: str,
    tags: list[str] | None = None,
) -> Iterator[_RequestTrace]:
    """Abre o trace raiz da requisição. Tudo que rodar dentro dele (classificador, agente,
    ferramentas) aparece aninhado no mesmo trace, agrupado por session_id (a conversa).

    Falha ao montar o trace nunca derruba o chat; exceções do corpo (`with`) passam intactas.
    """
    stack = ExitStack()
    trace = _RequestTrace(None)
    if _enabled:
        try:
            from langfuse import get_client, propagate_attributes

            span = stack.enter_context(
                get_client().start_as_current_observation(
                    as_type="span", name=name, input=input_text
                )
            )
            stack.enter_context(
                propagate_attributes(
                    trace_name=name,
                    session_id=session_id,
                    user_id=user_id,
                    tags=tags or [],
                )
            )
            trace = _RequestTrace(span)
        except Exception:
            logger.warning("tracing.trace_failed", stage="tracing", exc_info=True)
            stack.close()
            stack = ExitStack()
            trace = _RequestTrace(None)
    with stack:
        yield trace


def record_score(name: str, value: float, comment: str | None = None) -> None:
    """Registra uma nota no trace atual (ex.: decisão do classificador de escopo)."""
    if not _enabled:
        return
    try:
        from langfuse import get_client

        get_client().score_current_trace(
            name=name, value=value, data_type="NUMERIC", comment=comment
        )
    except Exception:
        logger.warning("tracing.score_failed", stage="tracing", exc_info=True)
