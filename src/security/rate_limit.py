"""Limite de requisições por janela fixa.

- RedisRateLimiter: compartilhado entre instâncias e sobrevive a deploys.
- InMemoryRateLimiter: sem Redis (1 instância; zera a cada reinício).
- FallbackRateLimiter: tenta o Redis e, se ele cair, usa a memória em vez de derrubar o chat.

Janela fixa permite um pico de até 2x o limite na virada da janela. Para um chat público
com limite baixo isso é aceitável e bem mais simples que janela deslizante.
"""

import time
from dataclasses import dataclass
from typing import Protocol

import structlog

from src.observability.metrics import REDIS_ERRORS

logger = structlog.get_logger()


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int  # segundos até a janela virar


class RateLimiter(Protocol):
    async def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitResult: ...

    async def close(self) -> None: ...


class InMemoryRateLimiter:
    _PURGE_THRESHOLD = 10_000

    def __init__(self) -> None:
        self._counters: dict[str, tuple[int, float]] = {}  # key -> (contagem, expira_em)

    def _purge(self, now: float) -> None:
        if len(self._counters) < self._PURGE_THRESHOLD:
            return
        self._counters = {k: v for k, v in self._counters.items() if v[1] > now}

    async def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = time.monotonic()
        self._purge(now)
        count, expires_at = self._counters.get(key, (0, 0.0))
        if expires_at <= now:
            count, expires_at = 0, now + window_seconds
        count += 1
        self._counters[key] = (count, expires_at)
        return RateLimitResult(
            allowed=count <= limit,
            limit=limit,
            remaining=max(0, limit - count),
            retry_after=max(1, int(expires_at - now) + 1),
        )

    async def close(self) -> None:
        self._counters.clear()


class RedisRateLimiter:
    def __init__(self, client) -> None:  # redis.asyncio.Redis
        self._redis = client

    async def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        # SET NX EX garante o TTL na primeira batida; tudo na mesma transação.
        pipe = self._redis.pipeline(transaction=True)
        pipe.set(key, 0, ex=window_seconds, nx=True)
        pipe.incr(key)
        pipe.ttl(key)
        _, count, ttl = await pipe.execute()
        retry_after = ttl if isinstance(ttl, int) and ttl > 0 else window_seconds
        return RateLimitResult(
            allowed=count <= limit,
            limit=limit,
            remaining=max(0, limit - count),
            retry_after=retry_after,
        )

    async def close(self) -> None:
        await self._redis.aclose()


class FallbackRateLimiter:
    """Usa o Redis; se falhar, cai para a memória por alguns segundos (sem esperar timeouts)."""

    COOLDOWN_SECONDS = 15.0

    def __init__(self, primary: RateLimiter, fallback: RateLimiter) -> None:
        self._primary = primary
        self._fallback = fallback
        self._skip_primary_until = 0.0

    async def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        if time.monotonic() >= self._skip_primary_until:
            try:
                return await self._primary.hit(key, limit, window_seconds)
            except Exception:
                REDIS_ERRORS.inc()
                self._skip_primary_until = time.monotonic() + self.COOLDOWN_SECONDS
                logger.warning("ratelimit.redis_failed", stage="rate_limit", exc_info=True)
        return await self._fallback.hit(key, limit, window_seconds)

    async def close(self) -> None:
        for limiter in (self._primary, self._fallback):
            try:
                await limiter.close()
            except Exception:
                logger.warning("ratelimit.close_failed", stage="shutdown", exc_info=True)


def build_rate_limiter(redis_url: str) -> RateLimiter:
    """Redis quando REDIS_URL existe (com fallback em memória); senão só memória."""
    memory = InMemoryRateLimiter()
    if not redis_url:
        return memory
    import redis.asyncio as redis

    client = redis.from_url(
        redis_url,
        socket_connect_timeout=0.5,
        socket_timeout=0.5,
        decode_responses=True,
    )
    return FallbackRateLimiter(RedisRateLimiter(client), memory)
