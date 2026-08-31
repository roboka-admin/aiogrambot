from unittest.mock import patch

import pytest

from services.system import SystemService


class FakeDatabase:
    async def get_db_stats(self):
        return 4, 12


@pytest.mark.asyncio
async def test_system_statistics_collects_bot_and_database_metrics():
    service = SystemService(database=FakeDatabase())
    service.record_update()
    service.record_update()
    service.record_error()
    stats = await service.get_system_statistics()
    assert stats.total_updates == 2
    assert stats.total_errors == 1
    assert stats.database_healthy is True
    assert stats.db_table_count == 4
    assert stats.db_row_count == 12
    assert stats.uptime_seconds >= 0
    assert stats.current_time.tzinfo is not None
    assert stats.cpu_percent is not None
    assert stats.memory_percent is not None
    assert stats.memory_used_mb is not None
    assert stats.memory_total_mb is not None
    assert stats.disk_percent is not None
    assert stats.disk_used_gb is not None
    assert stats.disk_total_gb is not None
    assert stats.server_uptime_seconds is not None


@pytest.mark.asyncio
async def test_system_statistics_handles_database_failure():
    class BrokenDatabase:
        async def get_db_stats(self):
            raise RuntimeError("database unavailable")

    service = SystemService(database=BrokenDatabase())
    stats = await service.get_system_statistics()
    assert stats.database_healthy is False
    assert stats.db_table_count == 0
    assert stats.db_row_count is None


@pytest.mark.asyncio
async def test_system_statistics_handles_psutil_failures_without_crashing():
    service = SystemService()

    with (
        patch("services.system.psutil.cpu_percent", side_effect=OSError("cpu unavailable")),
        patch("services.system.psutil.virtual_memory", side_effect=RuntimeError("memory unavailable")),
        patch("services.system.psutil.disk_usage", side_effect=OSError("disk unavailable")),
        patch("services.system.psutil.boot_time", side_effect=ValueError("boot time unavailable")),
    ):
        stats = await service.get_system_statistics()

    assert stats.cpu_percent is None
    assert stats.memory_percent is None
    assert stats.memory_used_mb is None
    assert stats.memory_total_mb is None
    assert stats.disk_percent is None
    assert stats.disk_used_gb is None
    assert stats.disk_total_gb is None
    assert stats.server_uptime_seconds is None
