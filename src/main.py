import hmac
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from src.api.middleware.limits import BodySizeLimitMiddleware, MetricsMiddleware
from src.api.middleware.request_id import RequestIDMiddleware
from src.api.v1.router import router as v1_router
from src.conversations.memory_repository import InMemoryConversationRepository
from src.core.config import get_settings
from src.core.exceptions import OceanAgentError
from src.observability.logging import configure_logging
from src.observability.metrics import render_metrics
from src.observability.tracing import init_tracing, shutdown_tracing
from src.security.rate_limit import build_rate_limiter

settings = get_settings()
configure_logging(settings.log_level)
init_tracing(settings)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await app.state.rate_limiter.close()
    shutdown_tracing()


app = FastAPI(
    title="Ocean Agent API",
    version="0.1.0",
    description="AI agent orchestration API with MCP tool integration",
    lifespan=lifespan,
)

# Ordem: o último adicionado é o mais externo. CORS fica por fora para que respostas
# de erro (413, 429) também levem os headers CORS e o navegador consiga lê-las.
app.add_middleware(MetricsMiddleware)
app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_body_bytes)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Client-Id", "X-Request-ID"],
    expose_headers=["X-Request-ID", "Retry-After"],
)

app.state.conversation_repository = InMemoryConversationRepository(
    max_conversations=settings.max_conversations,
    max_messages_per_conversation=settings.max_messages_per_conversation,
)
app.state.rate_limiter = build_rate_limiter(settings.redis_url)
app.include_router(v1_router)


@app.exception_handler(OceanAgentError)
async def ocean_agent_error_handler(request: Request, exc: OceanAgentError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": "an internal service error occurred"})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("request.failed", stage="request_failed", error_type=type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "internal server error"})


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ocean-agent-api"}


@app.get("/metrics", include_in_schema=False)
async def metrics(request: Request) -> Response:
    """Métricas Prometheus. Em produção exige METRICS_TOKEN (Bearer); sem token, fica desligado."""
    current = get_settings()
    if current.metrics_token:
        provided = request.headers.get("authorization", "")
        if not hmac.compare_digest(provided, f"Bearer {current.metrics_token}"):
            raise HTTPException(status_code=401, detail="unauthorized")
    elif current.environment != "development":
        raise HTTPException(status_code=404, detail="not found")
    body, content_type = render_metrics()
    return Response(content=body, media_type=content_type)
