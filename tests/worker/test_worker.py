import fakeredis.aioredis

from src.worker import collectors, settings as worker_settings
from src.worker.cache import cache_get, cache_set


async def test_cache_roundtrip_keeps_collection_time_and_ttl():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await cache_set(redis, "mare_santos", {"altura_m": 1.2}, ttl_seconds=60)
    cached = await cache_get(redis, "mare_santos")
    assert cached["data"] == {"altura_m": 1.2}
    assert cached["collected_at"] > 0
    assert 0 < await redis.ttl("ocean:src:mare_santos") <= 60
    assert await cache_get(redis, "inexistente") is None


async def test_one_failing_collector_does_not_stop_the_others(monkeypatch):
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def good():
        return {"ok": True}

    async def bad():
        raise RuntimeError("site fora do ar")

    monkeypatch.setitem(collectors.COLLECTORS, "bom", collectors.Collector(good, 60))
    monkeypatch.setitem(collectors.COLLECTORS, "ruim", collectors.Collector(bad, 60))

    result = await worker_settings.run_collectors({"redis": redis})

    assert result == {"bom": "ok", "ruim": "error"}
    assert (await cache_get(redis, "bom"))["data"] == {"ok": True}
    assert await cache_get(redis, "ruim") is None
