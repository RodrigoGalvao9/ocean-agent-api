from src.agent.reviewer import deterministic_response_review


def test_deterministic_review_rejects_empty_and_unsafe_answers():
    assert "A resposta está vazia." in deterministic_response_review("")
    issues = deterministic_response_review("É seguro navegar hoje.")
    assert "A resposta faz afirmação insegura sobre navegação ou pesca." in issues


def test_deterministic_review_accepts_factual_caution():
    assert deterministic_response_review(
        "Ondas de 1,2 m em Recife. Consulte os avisos oficiais da Marinha."
    ) == []
