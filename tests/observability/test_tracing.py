import pytest

from src.observability import tracing


def test_disabled_tracing_is_a_noop_and_propagates_errors():
    assert not tracing.tracing_enabled()
    assert tracing.get_callbacks() == []
    tracing.record_score("x", 1.0)  # não pode lançar
    with tracing.trace_request(name="t", session_id="s", user_id="u", input_text="oi") as trace:
        trace.set_output("ok")
    with pytest.raises(ValueError):
        with tracing.trace_request(name="t", session_id="s", user_id="u", input_text="oi"):
            raise ValueError("erro do corpo precisa passar intacto")


def test_enabled_tracing_exports_real_spans_with_session_and_scores(monkeypatch):
    """Exercita o SDK real do Langfuse com um exportador em memória (sem rede)."""
    from langfuse import Langfuse, get_client
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    Langfuse(
        public_key="pk-lf-test",
        secret_key="sk-lf-test",
        host="http://127.0.0.1:9",
        span_exporter=exporter,
        flush_at=1,
    )
    scores = []
    monkeypatch.setattr(
        Langfuse, "score_current_trace", lambda self, **kw: scores.append(kw)
    )
    monkeypatch.setattr(tracing, "_enabled", True)

    assert len(tracing.get_callbacks()) == 1
    with tracing.trace_request(
        name="ocean-chat", session_id="conv-1", user_id="hash", input_text="oi", tags=["test"]
    ) as trace:
        tracing.record_score("scope_in_scope", 1.0, "teste")
        trace.set_output("resposta")
    with pytest.raises(ValueError):
        with tracing.trace_request(name="t", session_id="s", user_id="u", input_text="x"):
            raise ValueError("boom")

    get_client().flush()
    spans = exporter.get_finished_spans()
    assert spans, "nenhum span exportado"
    root = next(sp for sp in spans if sp.name == "ocean-chat")
    attrs = dict(root.attributes)
    assert attrs.get("session.id") == "conv-1"
    assert attrs.get("user.id") == "hash"
    assert scores == [
        {"name": "scope_in_scope", "value": 1.0, "data_type": "NUMERIC", "comment": "teste"}
    ]
