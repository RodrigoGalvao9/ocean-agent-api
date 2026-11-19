from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    query: str
    discovered_tools: list[dict[str, Any]]
    retrieval: dict[str, Any] | None
    context: str
    sources: list[dict[str, Any]]
    response: str
