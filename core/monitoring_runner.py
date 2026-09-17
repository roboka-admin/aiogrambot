"""Run the monitoring service on a fixed interval as an asyncio task."""

from __future__ import annotations

import asyncio
import logging

from services.monitoring import MonitoringService

logger = logging.getLogger(__name__)


async def _loop(service: MonitoringService, interval_seconds: int) -> None:
    # First cycle shortly after start so a broken deploy is reported fast,
    # but not immediately: give the DB pool and admin bootstrap a moment.
    await asyncio.sleep(min(30, interval_seconds))
    while True:
        try:
            await service.run_cycle()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Monitoring cycle failed")
        await asyncio.sleep(interval_seconds)


def start_monitoring(service: MonitoringService, *, interval_seconds: int) -> asyncio.Task[None]:
    logger.info("Monitoring enabled: every %s seconds", interval_seconds)
    return asyncio.create_task(_loop(service, interval_seconds), name="monitoring")


async def stop_monitoring(task: asyncio.Task[None] | None) -> None:
    if task is None or task.done():
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
