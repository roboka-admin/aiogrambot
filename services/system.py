import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import psutil

from core.timezone import tehran_now

if TYPE_CHECKING:
    from core.database import Database

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SystemStats:
    """System statistics snapshot."""

    bot_started_at: datetime
    current_time: datetime
    uptime_seconds: int
    server_uptime_seconds: int | None
    total_updates: int
    total_errors: int
    cpu_percent: float | None
    memory_percent: float | None
    memory_used_mb: int | None
    memory_total_mb: int | None
    disk_percent: float | None
    disk_used_gb: float | None
    disk_total_gb: float | None
    database_healthy: bool
    db_table_count: int
    db_row_count: int | None = None


class SystemService:
    """Tracks process and server-level statistics for the bot."""

    def __init__(self, *, database: "Database | None" = None) -> None:
        self._started_at = tehran_now()
        self._started_monotonic = time.monotonic()
        self._total_updates = 0
        self._total_errors = 0
        self._database = database
        psutil.cpu_percent(interval=None)

    def record_update(self) -> None:
        self._total_updates += 1

    def record_error(self) -> None:
        self._total_errors += 1

    async def get_system_statistics(self) -> SystemStats:
        db_healthy = False
        db_table_count = 0
        db_row_count: int | None = None

        if self._database:
            try:
                db_table_count, db_row_count = await self._database.get_db_stats()
                db_healthy = True
            except Exception:
                logger.exception("Failed to collect database statistics")

        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        return SystemStats(
            bot_started_at=self._started_at,
            current_time=tehran_now(),
            uptime_seconds=max(0, int(time.monotonic() - self._started_monotonic)),
            server_uptime_seconds=self._server_uptime(),
            total_updates=self._total_updates,
            total_errors=self._total_errors,
            cpu_percent=round(psutil.cpu_percent(interval=None), 1),
            memory_percent=round(memory.percent, 1),
            memory_used_mb=memory.used // (1024**2),
            memory_total_mb=memory.total // (1024**2),
            disk_percent=round(disk.percent, 1),
            disk_used_gb=round(disk.used / (1024**3), 2),
            disk_total_gb=round(disk.total / (1024**3), 2),
            database_healthy=db_healthy,
            db_table_count=db_table_count,
            db_row_count=db_row_count,
        )

    @staticmethod
    def _server_uptime() -> int | None:
        try:
            return max(0, int(time.time() - psutil.boot_time()))
        except (OSError, ValueError, RuntimeError):
            logger.exception("Failed to collect server uptime")
            return None
