"""Cache das coletas (APIs/scraping) no Redis. A API lê daqui; o worker escreve."""

import json
import time
from typing import Any

PREFIX = "ocean:src:"
HEARTBEAT_KEY = "ocean:worker:heartbeat"


async def cache_set(redis, name: str, data: Any, ttl_seconds: int) -> None:
    """Guarda o dado com a hora da coleta, para a resposta poder citar fonte e data."""
    payload = {"collected_at": int(time.time()), "data": data}
    await redis.set(PREFIX + name, json.dumps(payload, ensure_ascii=False), ex=ttl_seconds)


async def cache_get(redis, name: str) -> dict[str, Any] | None:
    raw = await redis.get(PREFIX + name)
    return json.loads(raw) if raw else None
