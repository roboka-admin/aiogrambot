import asyncio

from services.system import SystemService


class FakeDatabase:
    async def get_db_stats(self):
        return 4, 12


def test_system_statistics_collects_bot_and_database_metrics():
    async def scenario() -> None:
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

    asyncio.run(scenario())


def test_system_statistics_handles_database_failure():
    class BrokenDatabase:
        async def get_db_stats(self):
            raise RuntimeError("database unavailable")

    async def scenario() -> None:
        service = SystemService(database=BrokenDatabase())
        stats = await service.get_system_statistics()

        assert stats.database_healthy is False
        assert stats.db_table_count == 0
        assert stats.db_row_count is None

    asyncio.run(scenario())
