from langchain_core.messages import AIMessage, HumanMessage

from src.agent.history import summarize_history


def test_history_keeps_recent_messages_and_summarizes_older():
    history = [
        HumanMessage(content="Qual a maré em Recife?"),
        AIMessage(content="A maré está em preamar às 10h."),
        HumanMessage(content="E amanhã?"),
        AIMessage(content="Preciso consultar a fonte."),
        HumanMessage(content="Qual a condição em Santos?"),
        AIMessage(content="Vou verificar."),
    ]

    summarized = summarize_history(history, keep_messages=2, max_summary_chars=120)

    assert len(summarized) == 3
    assert summarized[0].content.startswith("Resumo do histórico anterior:")
    assert summarized[-2].content == "Qual a condição em Santos?"
    assert summarized[-1].content == "Vou verificar."
