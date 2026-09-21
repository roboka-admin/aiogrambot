import pytest

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


@pytest.fixture
def service_and_repository():
    repository = FakeAntiSpamRepository()
    return AntiSpamService(antispam_repository=repository), repository


@pytest.mark.asyncio
async def test_record_warning_and_block(service_and_repository):
    service, repository = service_and_repository
    warning = await service.record_warning(123)
    block = await service.record_block(123)
    assert warning.user_telegram_id == 123
    assert warning.event_type == AntiSpamEventType.WARNING
    assert block.user_telegram_id == 123
    assert block.event_type == AntiSpamEventType.BLOCK
    assert len(repository.events) == 2


@pytest.mark.asyncio
async def test_antispam_statistics_count_recorded_events(service_and_repository):
    service, _ = service_and_repository
    await service.record_warning(123)
    await service.record_warning(456)
    await service.record_block(123)
    statistics = await service.get_antispam_statistics()
    assert statistics["total_warnings"] == 2
    assert statistics["total_blocks"] == 1
    assert statistics["today"] == 3
    assert statistics["last_7_days"] == 3
    assert statistics["last_30_days"] == 3


class FakeCounterRepository:
    def __init__(self, values: dict[str, int]) -> None:
        self.values = values

    async def add(self, kind: str, amount: int) -> None:
        self.values[kind] = self.values.get(kind, 0) + amount

    async def get(self, kind: str) -> int:
        return self.values.get(kind, 0)


@pytest.mark.asyncio
async def test_lifetime_totals_include_rows_archived_by_retention():
    repository = FakeAntiSpamRepository()
    counters = FakeCounterRepository({"antispam_warnings": 40, "antispam_blocks": 3})
    service = AntiSpamService(antispam_repository=repository, counter_repository=counters)

    await service.record_warning(1)
    await service.record_block(1)

    statistics = await service.get_antispam_statistics()
    assert statistics["total_warnings"] == 41
    assert statistics["total_blocks"] == 4
    assert statistics["today"] == 2  # windows only ever look at live rows
