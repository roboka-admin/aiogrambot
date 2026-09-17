import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import psutil

from core.cgroup import read_cgroup_memory
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
    db_latency_ms: float | None = None
    db_size_mb: float | None = None


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
        db_latency_ms: float | None = None
        db_size_mb: float | None = None

        if self._database:
            try:
                db_latency_ms = await self._database.ping()
                db_table_count, db_row_count = await self._database.get_db_stats()
                db_healthy = True
            except Exception:
                logger.exception("Failed to collect database statistics")
            else:
                try:
                    size_bytes = await self._database.get_db_size_bytes()
                except Exception:
                    logger.exception("Failed to collect database size")
                else:
                    if size_bytes is not None:
                        db_size_mb = round(size_bytes / (1024**2), 2)

        cpu_percent = self._cpu_percent()
        memory_info = self._memory_info()
        disk_info = self._disk_info()

        return SystemStats(
            bot_started_at=self._started_at,
            current_time=tehran_now(),
            uptime_seconds=max(0, int(time.monotonic() - self._started_monotonic)),
            server_uptime_seconds=self._server_uptime(),
            total_updates=self._total_updates,
            total_errors=self._total_errors,
            cpu_percent=cpu_percent,
            memory_percent=memory_info[2] if memory_info else None,
            memory_used_mb=memory_info[0] if memory_info else None,
            memory_total_mb=memory_info[1] if memory_info else None,
            disk_percent=disk_info[2] if disk_info else None,
            disk_used_gb=disk_info[0] if disk_info else None,
            disk_total_gb=disk_info[1] if disk_info else None,
            database_healthy=db_healthy,
            db_table_count=db_table_count,
            db_row_count=db_row_count,
            db_latency_ms=db_latency_ms,
            db_size_mb=db_size_mb,
        )

    @staticmethod
    def _cpu_percent() -> float | None:
        try:
            return round(psutil.cpu_percent(interval=None), 1)
        except (OSError, RuntimeError):
            logger.exception("Failed to collect CPU usage")
            return None

    @staticmethod
    def _memory_info() -> tuple[int, int, float] | None:
        # Inside a container the cgroup limit is the real ceiling; psutil
        # would report the host machine instead.
        cgroup = read_cgroup_memory()
        if cgroup is not None:
            return (
                cgroup.used_bytes // (1024**2),
                cgroup.limit_bytes // (1024**2),
                cgroup.percent,
            )
        try:
            memory = psutil.virtual_memory()
            return (
                memory.used // (1024**2),
                memory.total // (1024**2),
                round(memory.percent, 1),
            )
        except (OSError, RuntimeError):
            logger.exception("Failed to collect memory usage")
            return None

    @staticmethod
    def _disk_info() -> tuple[float, float, float] | None:
        try:
            disk = psutil.disk_usage("/")
            return (
                round(disk.used / (1024**3), 2),
                round(disk.total / (1024**3), 2),
                round(disk.percent, 1),
            )
        except (OSError, RuntimeError):
            logger.exception("Failed to collect disk usage")
            return None

    @staticmethod
    def _server_uptime() -> int | None:
        try:
            return max(0, int(time.time() - psutil.boot_time()))
        except (OSError, ValueError, RuntimeError):
            logger.exception("Failed to collect server uptime")
            return None
