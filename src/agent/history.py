from collections.abc import Sequence

from langchain_core.messages import BaseMessage, HumanMessage


def summarize_history(
    history: Sequence[BaseMessage],
    *,
    keep_messages: int = 4,
    max_summary_chars: int = 600,
) -> list[BaseMessage]:
    if len(history) <= keep_messages:
        return list(history)

    older = history[:-keep_messages]
    recent = history[-keep_messages:]
    parts: list[str] = []
    for message in older:
        role = "Usuário" if isinstance(message, HumanMessage) else "Assistente"
        text = str(message.content).replace("\n", " ").strip()
        if text:
            parts.append(f"{role}: {text[:160]}")
    summary = " | ".join(parts)
    if len(summary) > max_summary_chars:
        summary = summary[: max_summary_chars - 1].rstrip() + "…"

    return [HumanMessage(content=f"Resumo do histórico anterior:\n{summary}"), *recent]
