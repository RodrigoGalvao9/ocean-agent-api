"""Métricas Prometheus (para o Grafana). Registro padrão, 1 processo uvicorn."""

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS = Counter(
    "ocean_http_requests_total",
    "Requisições HTTP",
    ["method", "route", "status"],
)
HTTP_LATENCY = Histogram(
    "ocean_http_request_duration_seconds",
    "Duração das requisições HTTP",
    ["method", "route"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
)
SCOPE_DECISIONS = Counter(
    "ocean_scope_decisions_total",
    "Decisões do portão de escopo",
    ["decision"],  # in_scope | out_of_scope | classifier_error
)
CHAT_OUTCOMES = Counter(
    "ocean_chat_outcomes_total",
    "Resultado final de cada pergunta",
    ["outcome"],  # answered | refused_scope | refused_no_sources | needs_clarification | rejected_validation | needs_clarification | rejected_validation
)
QUESTION_ROUTES = Counter(
    "ocean_question_routes_total",
    "Rotas estruturadas escolhidas pelo refinador",
    ["route"],  # simple | live_data | knowledge | complex
)
RESPONSE_VALIDATIONS = Counter(
    "ocean_response_validations_total",
    "Resultado da validação LLM de respostas complexas",
    ["result"],  # approved | rejected | unavailable | deterministic_rejected
)
MCP_CALLS = Counter(
    "ocean_mcp_calls_total",
    "Chamadas ao servidor MCP",
    ["operation", "status"],  # list_tools|invoke_tool, ok|error
)
MCP_LATENCY = Histogram(
    "ocean_mcp_call_duration_seconds",
    "Duração das chamadas ao MCP",
    ["operation"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
)
MCP_TOOL_CALLS = Counter(
    "ocean_mcp_tool_calls_total",
    "Chamadas por ferramenta MCP",
    ["tool", "status"],  # status: ok | partial | stale | unavailable | error
)
MCP_TOOL_LATENCY = Histogram(
    "ocean_mcp_tool_duration_seconds",
    "Duração das chamadas por ferramenta MCP",
    ["tool"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
)
RATE_LIMIT_HITS = Counter(
    "ocean_rate_limit_rejections_total",
    "Requisições recusadas por limite",
    ["scope"],  # client_minute | client_day | global_minute | read_minute
)
REDIS_ERRORS = Counter(
    "ocean_redis_errors_total",
    "Falhas do Redis (o limite cai para memória)",
)


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
