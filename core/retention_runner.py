"""Run event-table retention on a fixed interval as an asyncio task."""

from __future__ import annotations

import asyncio
import logging

from services.retention import RetentionService

logger = logging.getLogger(__name__)


async def _loop(service: RetentionService, interval_seconds: int) -> None:
    # Give startup (pool, migrations, admin bootstrap) a minute before the
    # first pass; afterwards run on the configured interval.
    await asyncio.sleep(min(60, interval_seconds))
    while True:
        try:
            await service.run_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Retention run failed")
        await asyncio.sleep(interval_seconds)


def start_retention(service: RetentionService, *, interval_seconds: int) -> asyncio.Task[None]:
    logger.info("Event retention enabled: every %s seconds", interval_seconds)
    return asyncio.create_task(_loop(service, interval_seconds), name="retention")


async def stop_retention(task: asyncio.Task[None] | None) -> None:
    if task is None or task.done():
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
