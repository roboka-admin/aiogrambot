import asyncio

from models.antispam import AntiSpamEventType
from services.antispam import AntiSpamService


class FakeAntiSpamRepository:
    def __init__(self) -> None:
        self.events = []

    async def create(self, event):
        self.events.append(event)
        return event

    async def count_total_warnings(self) -> int:
        return sum(event.event_type == AntiSpamEventType.WARNING for event in self.events)

    async def count_total_blocks(self) -> int:
        return sum(event.event_type == AntiSpamEventType.BLOCK for event in self.events)

    async def count_today(self, today_start) -> int:
        return sum(event.created_at >= today_start for event in self.events)

    async def count_last_7_days(self, seven_days_ago) -> int:
        return sum(event.created_at >= seven_days_ago for event in self.events)

    async def count_last_30_days(self, thirty_days_ago) -> int:
        return sum(event.created_at >= thirty_days_ago for event in self.events)


def test_record_warning_and_block():
    async def scenario() -> None:
        repository = FakeAntiSpamRepository()
        service = AntiSpamService(antispam_repository=repository)

        warning = await service.record_warning(123)
        block = await service.record_block(123)

        assert warning.user_telegram_id == 123
        assert warning.event_type == AntiSpamEventType.WARNING
        assert block.user_telegram_id == 123
        assert block.event_type == AntiSpamEventType.BLOCK
        assert len(repository.events) == 2

    asyncio.run(scenario())


def test_antispam_statistics_count_recorded_events():
    async def scenario() -> None:
        repository = FakeAntiSpamRepository()
        service = AntiSpamService(antispam_repository=repository)

        await service.record_warning(123)
        await service.record_warning(456)
        await service.record_block(123)

        statistics = await service.get_antispam_statistics()

        assert statistics["total_warnings"] == 2
        assert statistics["total_blocks"] == 1
        assert statistics["today"] == 3
        assert statistics["last_7_days"] == 3
        assert statistics["last_30_days"] == 3

    asyncio.run(scenario())
