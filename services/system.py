import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from typing import TYPE_CHECKING

from core.timezone import tehran_now

if TYPE_CHECKING:
    from core.database import Database


@dataclass(slots=True)
class SystemStats:
    """System statistics snapshot."""

    bot_started_at: datetime
    uptime_seconds: int
    total_updates: int
    total_errors: int
    db_table_count: int
    db_row_count: int | None = None


class SystemService:
    """Tracks system-level statistics for the bot."""

    def __init__(self, *, database: "Database | None" = None) -> None:
        self._started_at: datetime = tehran_now()
        self._total_updates: int = 0
        self._total_errors: int = 0
        self._database = database

    def record_update(self) -> None:
        self._total_updates += 1

    def record_error(self) -> None:
        self._total_errors += 1

    async def get_system_statistics(self) -> SystemStats:
        uptime = int(time.monotonic() - self._started_at.timestamp())

        db_table_count = 0
        db_row_count: int | None = None

        if self._database:
            try:
                db_table_count, db_row_count = await self._database.get_db_stats()
            except Exception:
                pass

        return SystemStats(
            bot_started_at=self._started_at,
            uptime_seconds=uptime,
            total_updates=self._total_updates,
            total_errors=self._total_errors,
            db_table_count=db_table_count,
            db_row_count=db_row_count,
        )
