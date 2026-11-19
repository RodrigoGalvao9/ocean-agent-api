from langchain_core.messages import AIMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
import structlog

from src.agent.prompts.system import SYSTEM_PROMPT
from src.core.config import Settings
from src.llm.provider import create_llm
from src.mcp.client import MCPClient
from src.mcp.tools import mcp_tools_to_langchain
from src.security.guardrails import validate_user_message


class OceanAgent:
    def __init__(self, settings: Settings, mcp_client: MCPClient | None = None) -> None:
        self.settings = settings
        self.mcp_client = mcp_client or MCPClient(settings)
        self.logger = structlog.get_logger()

    async def run(self, message: str) -> str:
        clean_message = validate_user_message(message)
        llm = create_llm(self.settings)

        tools = []
        try:
            discovered = await self.mcp_client.list_tools()
            tools = mcp_tools_to_langchain(discovered, self.mcp_client)
            self.logger.info("mcp.tools_discovered", stage="mcp_tool_discovery", count=len(tools))
        except Exception:
            tools = []

        graph = create_react_agent(llm, tools=tools, prompt=SYSTEM_PROMPT)
        self.logger.info("llm.execution_started", stage="llm_execution")
        result = await graph.ainvoke({"messages": [HumanMessage(content=clean_message)]})

        messages = result.get("messages", [])
        if messages:
            final = messages[-1]
            if isinstance(final, AIMessage):
                return str(final.content)
        raise RuntimeError("agent did not produce a response")
