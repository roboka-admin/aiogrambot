from contextlib import asynccontextmanager

import pytest

from models.broadcast import BroadcastRecord
from services.broadcast import BroadcastProgress, BroadcastService


class FakeUserRepository:
    async def list_active_telegram_ids(self, *, registered_only: bool = False) -> list[int]:
        return [1, 2]


class FakeBroadcastRepository:
    def __init__(self) -> None:
        self.records: list[BroadcastRecord] = []

    async def create(self, record: BroadcastRecord) -> BroadcastRecord:
        self.records.append(record)
        return record

    async def count_total(self) -> int:
        return len(self.records)

    async def count_today(self, today_start):
        return 0

    async def count_last_7_days(self, start):
        return 0

    async def count_last_30_days(self, start):
        return 0

    async def get_latest(self):
        return self.records[-1] if self.records else None


class FakeBot:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def copy_message(self, *, chat_id: int, from_chat_id: int, message_id: int) -> None:
        self.events.append(f"telegram:{chat_id}")


@pytest.mark.asyncio
async def test_broadcast_database_scopes_do_not_wrap_telegram_delivery():
    events: list[str] = []
    user_repository = FakeUserRepository()
    broadcast_repository = FakeBroadcastRepository()

    @asynccontextmanager
    async def repository_factory():
        events.append("db:begin")
        try:
            yield user_repository, broadcast_repository
        finally:
            events.append("db:end")

    service = BroadcastService(
        bot=FakeBot(events),
        repository_factory=repository_factory,
    )

    async def progress(_: BroadcastProgress) -> None:
        events.append("progress")

    result = await service.broadcast(
        from_chat_id=10,
        message_id=20,
        progress_callback=progress,
        progress_interval=1,
    )

    assert result.total == 2
    assert events.index("db:end") < events.index("telegram:1")
    assert events.index("telegram:2") < events.index("db:begin", 1)
    assert events[-1] == "db:end"
    assert len(broadcast_repository.records) == 1
