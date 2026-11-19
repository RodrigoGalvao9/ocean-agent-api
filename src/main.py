from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.middleware.request_id import RequestIDMiddleware
from src.api.v1.router import router as v1_router
from src.conversations.memory_repository import InMemoryConversationRepository
from src.core.config import get_settings
from src.core.exceptions import OceanAgentError
from src.observability.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title="Ocean Agent API",
    version="0.1.0",
    description="AI agent orchestration API with MCP tool integration",
)
app.add_middleware(RequestIDMiddleware)
app.state.conversation_repository = InMemoryConversationRepository()
app.include_router(v1_router)


@app.exception_handler(OceanAgentError)
async def ocean_agent_error_handler(request: Request, exc: OceanAgentError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": "an internal service error occurred"})


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ocean-agent-api"}
