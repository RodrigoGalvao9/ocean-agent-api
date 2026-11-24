from src.agent.reviewer import deterministic_response_review
from src.agent.refiner import (
    deterministic_refinement,
    needs_llm_refinement,
    normalize_marine_terms,
)


def test_deterministic_review_rejects_empty_and_unsafe_answers():
    assert "A resposta está vazia." in deterministic_response_review("")
    issues = deterministic_response_review("É seguro navegar hoje.")
    assert "A resposta faz afirmação insegura sobre navegação ou pesca." in issues


def test_deterministic_review_accepts_factual_caution():
    assert deterministic_response_review(
        "Ondas de 1,2 m em Recife. Consulte os avisos oficiais da Marinha."
    ) == []


def test_pre_amar_variants_are_normalized():
    assert normalize_marine_terms("Qual a pre amar em Santos?") == "Qual a preamar em Santos?"
    assert normalize_marine_terms("Qual a pré-mar em Recife?") == "Qual a preamar em Recife?"


def test_clear_questions_skip_external_refiner():
    assert not needs_llm_refinement("Qual a preamar em Santos?")
    assert not needs_llm_refinement("Como está o mar em Recife?")
    assert needs_llm_refinement("Como está o mar?")
    assert needs_llm_refinement("E amanhã?", history=[])


def test_deterministic_refinement_detects_route():
    assert deterministic_refinement("Compare a maré em Recife e Santos").route == "complex"
    assert deterministic_refinement("O que é preamar").route == "knowledge"


def test_deterministic_review_blocks_claims_that_fishing_is_open():
    from src.agent.reviewer import deterministic_response_review as review

    assert review("Você pode pescar lagosta agora.")
    assert review("A pesca está liberada em Recife.")
    assert not review("Hoje a lagosta está em defeso; não pode pescar até 30/04.")
    assert not review("Não encontrei defeso, mas isso não significa que a pesca não está liberada.")
