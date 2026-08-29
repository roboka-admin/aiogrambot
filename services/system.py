import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

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

        return SystemStats(
            bot_started_at=self._started_at,
            current_time=tehran_now(),
            uptime_seconds=max(0, int(time.monotonic() - self._started_monotonic)),
            server_uptime_seconds=self._server_uptime(),
            total_updates=self._total_updates,
            total_errors=self._total_errors,
            cpu_percent=self._cpu_percent(),
            memory_percent=self._memory_percent(),
            memory_used_mb=self._memory_used_mb(),
            memory_total_mb=self._memory_total_mb(),
            disk_percent=self._disk_percent(),
            disk_used_gb=self._disk_used_gb(),
            disk_total_gb=self._disk_total_gb(),
            database_healthy=db_healthy,
            db_table_count=db_table_count,
            db_row_count=db_row_count,
        )

    @staticmethod
    def _server_uptime() -> int | None:
        try:
            with open("/proc/uptime", encoding="utf-8") as file:
                return int(float(file.readline().split()[0]))
        except (OSError, ValueError, IndexError):
            return None

    @staticmethod
    def _memory_info() -> tuple[int, int] | None:
        try:
            values: dict[str, int] = {}
            with open("/proc/meminfo", encoding="utf-8") as file:
                for line in file:
                    key, value, *_ = line.split()
                    if key in {"MemTotal:", "MemAvailable:"}:
                        values[key] = int(value)
            if "MemTotal:" in values and "MemAvailable:" in values:
                total = values["MemTotal:"] // 1024
                available = values["MemAvailable:"] // 1024
                return total, max(0, total - available)
        except (OSError, ValueError, IndexError):
            pass
        return None

    @classmethod
    def _memory_total_mb(cls) -> int | None:
        info = cls._memory_info()
        return info[0] if info else None

    @classmethod
    def _memory_used_mb(cls) -> int | None:
        info = cls._memory_info()
        return info[1] if info else None

    @classmethod
    def _memory_percent(cls) -> float | None:
        info = cls._memory_info()
        if info and info[0]:
            return round((info[1] / info[0]) * 100, 1)
        return None

    @staticmethod
    def _cpu_percent() -> float | None:
        try:
            with open("/proc/loadavg", encoding="utf-8") as file:
                load = float(file.readline().split()[0])
            return round(min(100.0, load / (os.cpu_count() or 1) * 100), 1)
        except (OSError, ValueError, IndexError):
            return None

    @staticmethod
    def _disk_usage() -> tuple[int, int] | None:
        try:
            usage = os.statvfs("/")
            total = usage.f_blocks * usage.f_frsize
            free = usage.f_bavail * usage.f_frsize
            return total, total - free
        except OSError:
            return None

    @classmethod
    def _disk_percent(cls) -> float | None:
        usage = cls._disk_usage()
        if usage and usage[0]:
            return round((usage[1] / usage[0]) * 100, 1)
        return None

    @classmethod
    def _disk_used_gb(cls) -> float | None:
        usage = cls._disk_usage()
        return round(usage[1] / (1024**3), 2) if usage else None

    @classmethod
    def _disk_total_gb(cls) -> float | None:
        usage = cls._disk_usage()
        return round(usage[0] / (1024**3), 2) if usage else None
