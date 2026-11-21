from datetime import datetime, timedelta, timezone

from src.agent.prompts.system import (
    REFUSAL_OUT_OF_SCOPE,
    SCOPE_CLASSIFIER_PROMPT,
    SYSTEM_PROMPT,
    build_system_prompt,
)


def test_prompt_covers_the_new_scope_and_drops_the_old_demo_language():
    for word in ("defeso", "embarcações", "pescado", "marés", "Marinha do Brasil"):
        assert word in SYSTEM_PROMPT
    assert "fictícios" not in SYSTEM_PROMPT
    assert "tempestade" not in SYSTEM_PROMPT.lower()


def test_prompt_enforces_safety_rules():
    assert "Nunca afirme que é seguro" in SYSTEM_PROMPT
    assert "bons pontos de pesca" in SYSTEM_PROMPT
    assert "não confiável" in SYSTEM_PROMPT


def test_system_prompt_includes_todays_date_in_brasilia_time():
    # 21/11/2026 02:30 UTC ainda é 20/11 em Brasília (UTC-3).
    now = datetime(2026, 11, 21, 2, 30, tzinfo=timezone.utc)
    prompt = build_system_prompt(now)
    assert "sexta-feira, 2026-11-20" in prompt
    assert "{today}" not in prompt
    assert build_system_prompt(now.astimezone(timezone(timedelta(hours=5)))) == prompt


def test_scope_classifier_accepts_fishing_and_tides():
    for word in ("defeso", "pesca", "marés", "embarcações"):
        assert word in SCOPE_CLASSIFIER_PROMPT
    assert "dúvida" in SCOPE_CLASSIFIER_PROMPT


def test_refusal_names_the_new_topics():
    assert "defeso" in REFUSAL_OUT_OF_SCOPE and "pescado" in REFUSAL_OUT_OF_SCOPE
