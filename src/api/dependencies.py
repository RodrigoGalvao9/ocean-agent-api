from collections.abc import Awaitable, Callable

import structlog
from fastapi import HTTPException, Request

from src.core.config import Settings, get_settings
from src.observability.metrics import RATE_LIMIT_HITS
from src.security.client import get_client_ip, ip_key, owner_key
from src.security.rate_limit import RateLimitResult

logger = structlog.get_logger()

MINUTE = 60
DAY = 86_400


def get_owner_id(request: Request) -> str:
    """Hash do dono da conversa (X-Client-Id ou IP). Nunca é devolvido ao cliente."""
    settings = get_settings()
    ip = get_client_ip(request, settings.trusted_proxy_hops)
    return owner_key(request, ip)


def _reject(scope: str, result: RateLimitResult) -> HTTPException:
    RATE_LIMIT_HITS.labels(scope=scope).inc()
    return HTTPException(
        status_code=429,
        detail=f"Muitas requisições. Tente novamente em {result.retry_after} segundos.",
        headers={
            "Retry-After": str(result.retry_after),
            "X-RateLimit-Limit": str(result.limit),
            "X-RateLimit-Remaining": "0",
        },
    )


def _chat_rules(settings: Settings, ip: str) -> list[tuple[str, str, int, int]]:
    """(escopo, chave, limite, janela). O global vem por último: só gasta se o cliente passou."""
    client = ip_key(ip)
    return [
        ("client_minute", f"ocean:rl:chat:m:{client}", settings.rate_limit_chat_per_minute, MINUTE),
        ("client_day", f"ocean:rl:chat:d:{client}", settings.rate_limit_chat_per_day, DAY),
        ("global_minute", "ocean:rl:chat:global:m", settings.rate_limit_global_per_minute, MINUTE),
    ]


def _read_rules(settings: Settings, ip: str) -> list[tuple[str, str, int, int]]:
    return [
        (
            "read_minute",
            f"ocean:rl:read:m:{ip_key(ip)}",
            settings.rate_limit_read_per_minute,
            MINUTE,
        )
    ]


def rate_limit(policy: str) -> Callable[[Request], Awaitable[None]]:
    rules_for = {"chat": _chat_rules, "read": _read_rules}[policy]

    async def dependency(request: Request) -> None:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return
        limiter = request.app.state.rate_limiter
        ip = get_client_ip(request, settings.trusted_proxy_hops)
        for scope, key, limit, window in rules_for(settings, ip):
            result = await limiter.hit(key, limit, window)
            if not result.allowed:
                logger.info("ratelimit.rejected", stage="rate_limit", scope=scope)
                raise _reject(scope, result)

    return dependency


rate_limit_chat = rate_limit("chat")
rate_limit_read = rate_limit("read")
