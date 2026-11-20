import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.observability.metrics import HTTP_LATENCY, HTTP_REQUESTS


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Recusa corpos grandes antes de qualquer processamento (Content-Length declarado)."""

    def __init__(self, app, max_bytes: int) -> None:
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next) -> Response:
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > self._max_bytes:
            return JSONResponse(status_code=413, content={"detail": "requisição grande demais"})
        return await call_next(request)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Contadores e latência por rota (usa o template da rota para não explodir cardinalidade)."""

    async def dispatch(self, request: Request, call_next) -> Response:
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route = request.scope.get("route")
            path = getattr(route, "path", "unmatched")
            if path != "/metrics":
                HTTP_REQUESTS.labels(request.method, path, str(status)).inc()
                HTTP_LATENCY.labels(request.method, path).observe(time.perf_counter() - started)
