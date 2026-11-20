"""Registro das coletas em segundo plano.

Cada coletor é uma função async que devolve dados serializáveis em JSON. O worker roda todos
periodicamente e guarda o resultado no Redis (src/worker/cache.py) com TTL.

Próximos passos: registrar aqui Open-Meteo Marine, avisos de mau tempo da Marinha, etc.
    COLLECTORS["open_meteo_santos"] = Collector(fetch_open_meteo_santos, ttl_seconds=1800)
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Collector:
    fetch: Callable[[], Awaitable[Any]]
    ttl_seconds: int


COLLECTORS: dict[str, Collector] = {}
