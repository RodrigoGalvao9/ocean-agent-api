"""Worker arq (fila e agendamento sobre Redis).

Rodar:   python -m arq src.worker.settings.WorkerSettings
Saúde:   python -m arq src.worker.settings.WorkerSettings --check
"""

import time

import structlog
from arq import cron
from arq.connections import RedisSettings

from src.core.config import get_settings
from src.observability.logging import configure_logging
from src.worker.cache import HEARTBEAT_KEY, cache_set
from src.worker.collectors import COLLECTORS

logger = structlog.get_logger()
settings = get_settings()


async def startup(ctx: dict) -> None:
    configure_logging(settings.log_level)
    logger.info("worker.started", stage="worker", collectors=sorted(COLLECTORS))


async def heartbeat(ctx: dict) -> None:
    """Sinal de vida: se a chave expirar, o worker parou."""
    await ctx["redis"].set(HEARTBEAT_KEY, int(time.time()), ex=180)


async def run_collectors(ctx: dict) -> dict[str, str]:
    """Roda cada coletor isoladamente: a falha de um não derruba os outros."""
    results: dict[str, str] = {}
    for name, collector in COLLECTORS.items():
        try:
            data = await collector.fetch()
            await cache_set(ctx["redis"], name, data, collector.ttl_seconds)
            results[name] = "ok"
        except Exception as exc:
            logger.warning(
                "worker.collector_failed", stage="worker", collector=name, error=str(exc)[:200]
            )
            results[name] = "error"
    return results


class WorkerSettings:
    functions = [run_collectors]
    cron_jobs = [
        cron(heartbeat, second={0}, run_at_startup=True),  # todo minuto
        cron(run_collectors, minute={0, 15, 30, 45}, run_at_startup=True),
    ]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(settings.redis_url or "redis://localhost:6379/0")
    health_check_interval = 30
    max_jobs = 5
    job_timeout = 120
    keep_result = 300
