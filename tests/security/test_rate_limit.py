from unittest.mock import AsyncMock

import fakeredis.aioredis
import pytest

from src.security import rate_limit as rl
from src.security.rate_limit import (
    FallbackRateLimiter,
    InMemoryRateLimiter,
    RedisRateLimiter,
)


async def test_in_memory_blocks_after_limit_and_reports_retry_after():
    limiter = InMemoryRateLimiter()
    results = [await limiter.hit("k", 2, 60) for _ in range(3)]
    assert [r.allowed for r in results] == [True, True, False]
    assert results[2].remaining == 0
    assert 1 <= results[2].retry_after <= 61


async def test_in_memory_window_resets(monkeypatch):
    clock = {"now": 1000.0}
    monkeypatch.setattr(rl.time, "monotonic", lambda: clock["now"])
    limiter = InMemoryRateLimiter()
    assert (await limiter.hit("k", 1, 10)).allowed
    assert not (await limiter.hit("k", 1, 10)).allowed
    clock["now"] += 11
    assert (await limiter.hit("k", 1, 10)).allowed


async def test_in_memory_keys_are_independent():
    limiter = InMemoryRateLimiter()
    assert (await limiter.hit("a", 1, 60)).allowed
    assert (await limiter.hit("b", 1, 60)).allowed


async def test_redis_limiter_counts_and_sets_ttl():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    limiter = RedisRateLimiter(client)
    first = await limiter.hit("ocean:k", 2, 60)
    await limiter.hit("ocean:k", 2, 60)
    third = await limiter.hit("ocean:k", 2, 60)
    assert first.allowed and first.remaining == 1
    assert not third.allowed
    assert 0 < await client.ttl("ocean:k") <= 60
    assert third.retry_after <= 60


async def test_fallback_uses_memory_when_redis_fails_and_skips_redis_during_cooldown():
    broken = AsyncMock()
    broken.hit.side_effect = ConnectionError("redis down")
    limiter = FallbackRateLimiter(broken, InMemoryRateLimiter())

    assert (await limiter.hit("k", 1, 60)).allowed
    assert not (await limiter.hit("k", 1, 60)).allowed  # a memória continua limitando
    assert broken.hit.await_count == 1  # cooldown: não insiste no Redis a cada requisição
