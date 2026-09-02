import asyncio
from contextlib import asynccontextmanager

import pytest

from models.broadcast import BroadcastRecord
from services.broadcast import BroadcastService


class FakeUserRepository:
    async def list_active_telegram_ids(self, *, registered_only: bool = False) -> list[int]:
        return [1]


class FakeBroadcastRepository:
    async def create(self, record: BroadcastRecord) -> BroadcastRecord:
        return record

    async def count_total(self) -> int:
        return 0

    async def count_today(self, today_start):
        return 0

    async def count_last_7_days(self, start):
        return 0

    async def count_last_30_days(self, start):
        return 0

    async def get_latest(self):
        return None


class FakeBot:
    def __init__(self, events: list[str], first_started: asyncio.Event, release_first: asyncio.Event) -> None:
        self.events = events
        self.first_started = first_started
        self.release_first = release_first
        self.calls = 0

    async def copy_message(self, *, chat_id: int, from_chat_id: int, message_id: int) -> None:
        self.calls += 1
        self.events.append(f"telegram:start:{self.calls}")
        if self.calls == 1:
            self.first_started.set()
            await self.release_first.wait()
        self.events.append(f"telegram:end:{self.calls}")


@pytest.mark.asyncio
async def test_broadcasts_are_serialized_by_shared_lock():
    events: list[str] = []
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    user_repository = FakeUserRepository()
    broadcast_repository = FakeBroadcastRepository()

    @asynccontextmanager
    async def repository_factory():
        yield user_repository, broadcast_repository

    lock = asyncio.Lock()
    bot = FakeBot(events, first_started, release_first)
    service = BroadcastService(
        bot=bot,
        repository_factory=repository_factory,
        broadcast_lock=lock,
    )

    first = asyncio.create_task(service.broadcast(from_chat_id=10, message_id=20))
    await first_started.wait()

    second = asyncio.create_task(service.broadcast(from_chat_id=10, message_id=21))
    await asyncio.sleep(0)

    assert bot.calls == 1
    assert events == ["telegram:start:1"]

    release_first.set()
    await asyncio.gather(first, second)

    assert bot.calls == 2
    assert events == [
        "telegram:start:1",
        "telegram:end:1",
        "telegram:start:2",
        "telegram:end:2",
    ]
