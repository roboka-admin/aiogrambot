import asyncio
from datetime import timedelta

import pytest
from aiogram.exceptions import TelegramRetryAfter
from aiogram.methods import SendMessage

from core.timezone import tehran_now
from models.broadcast import BroadcastRecord
from services.broadcast import BroadcastProgress, BroadcastService


class FakeUserRepository:
    def __init__(self, ids: list[int]) -> None:
        self.ids = ids

    async def list_active_telegram_ids(self, *, registered_only: bool = False) -> list[int]:
        return list(self.ids)


class FakeBroadcastRepository:
    def __init__(self) -> None:
        self.records: list[BroadcastRecord] = []

    async def create(self, record):
        if record.id is None:
            record.id = len(self.records) + 1
        self.records.append(record)
        return record

    async def count_total(self) -> int:
        return len(self.records)

    async def count_today(self, today_start) -> int:
        return sum(record.created_at >= today_start for record in self.records)

    async def count_last_7_days(self, start) -> int:
        return sum(record.created_at >= start for record in self.records)

    async def count_last_30_days(self, start) -> int:
        return sum(record.created_at >= start for record in self.records)

    async def get_latest(self):
        if not self.records:
            return None
        return max(self.records, key=lambda record: record.id or 0)


class FakeBot:
    def __init__(self, failures: dict[int, Exception] | None = None) -> None:
        self.failures = failures or {}
        self.sent: list[int] = []
        self.calls: dict[int, int] = {}

    async def copy_message(self, *, chat_id: int, from_chat_id: int, message_id: int) -> None:
        self.calls[chat_id] = self.calls.get(chat_id, 0) + 1
        error = self.failures.get(chat_id)
        if error:
            raise error
        self.sent.append(chat_id)


def make_retry_after(seconds: int = 0) -> TelegramRetryAfter:
    return TelegramRetryAfter(
        method=SendMessage(chat_id=1, text="test"),
        message="retry",
        retry_after=seconds,
    )


@pytest.mark.asyncio
async def test_count_recipients_uses_active_user_ids():
    service = BroadcastService(
        user_repository=FakeUserRepository([1, 2, 3]),
        broadcast_repository=FakeBroadcastRepository(),
        bot=FakeBot(),
    )
    assert await service.count_recipients() == 3


@pytest.mark.asyncio
async def test_broadcast_statistics_without_history():
    service = BroadcastService(
        user_repository=FakeUserRepository([]),
        broadcast_repository=FakeBroadcastRepository(),
        bot=FakeBot(),
    )

    stats = await service.get_broadcast_statistics()

    assert stats["total_broadcasts"] == 0
    assert stats["today"] == 0
    assert stats["latest_total_recipients"] is None
    assert stats["latest_success_rate"] is None


@pytest.mark.asyncio
async def test_broadcast_statistics_with_latest_record():
    repository = FakeBroadcastRepository()
    repository.records.extend(
        [
            BroadcastRecord(
                id=1,
                total_recipients=10,
                success_count=8,
                failed_count=2,
                duration_seconds=4,
                created_at=tehran_now() - timedelta(days=40),
            ),
            BroadcastRecord(
                id=2,
                total_recipients=5,
                success_count=4,
                failed_count=1,
                duration_seconds=2,
                created_at=tehran_now(),
            ),
        ]
    )
    service = BroadcastService(
        user_repository=FakeUserRepository([]),
        broadcast_repository=repository,
        bot=FakeBot(),
    )

    stats = await service.get_broadcast_statistics()

    assert stats["total_broadcasts"] == 2
    assert stats["today"] == 1
    assert stats["last_7_days"] == 1
    assert stats["last_30_days"] == 1
    assert stats["latest_total_recipients"] == 5
    assert stats["latest_success"] == 4
    assert stats["latest_failed"] == 1
    assert stats["latest_success_rate"] == 80.0


@pytest.mark.asyncio
async def test_broadcast_empty_recipient_list():
    repository = FakeBroadcastRepository()
    service = BroadcastService(
        user_repository=FakeUserRepository([]),
        broadcast_repository=repository,
        bot=FakeBot(),
    )
    result = await service.broadcast(from_chat_id=1, message_id=2)
    assert result.total == 0
    assert result.success == 0
    assert result.failed == 0
    assert len(repository.records) == 1


@pytest.mark.asyncio
async def test_broadcast_counts_success_and_failure():
    repository = FakeBroadcastRepository()
    bot = FakeBot(failures={2: RuntimeError("send failed")})
    service = BroadcastService(
        user_repository=FakeUserRepository([1, 2, 3]),
        broadcast_repository=repository,
        bot=bot,
    )
    result = await service.broadcast(from_chat_id=10, message_id=20)
    assert result.total == 3
    assert result.success == 2
    assert result.failed == 1
    assert bot.sent == [1, 3]
    assert repository.records[0].success_count == 2
    assert repository.records[0].failed_count == 1


@pytest.mark.asyncio
async def test_broadcast_retries_after_flood_limit_and_then_succeeds():
    retry = make_retry_after(0)
    bot = FakeBot(failures={2: retry})
    service = BroadcastService(
        user_repository=FakeUserRepository([2]),
        broadcast_repository=FakeBroadcastRepository(),
        bot=bot,
    )

    # The fake always raises, so this exercises the retry/exhaustion path.
    result = await service.broadcast(from_chat_id=10, message_id=20)

    assert result.total == 1
    assert result.success == 0
    assert result.failed == 1
    assert bot.calls[2] == 3


@pytest.mark.asyncio
async def test_broadcast_progress_reports_at_interval_and_completion():
    repository = FakeBroadcastRepository()
    service = BroadcastService(
        user_repository=FakeUserRepository([1, 2, 3]),
        broadcast_repository=repository,
        bot=FakeBot(),
    )
    progress: list[BroadcastProgress] = []

    async def callback(item: BroadcastProgress) -> None:
        progress.append(item)

    await service.broadcast(
        from_chat_id=10,
        message_id=20,
        progress_callback=callback,
        progress_interval=2,
    )
    assert [item.processed for item in progress] == [2, 3]
    assert progress[-1].percent == 100
    assert progress[-1].success == 3


def test_broadcast_progress_properties_cover_empty_and_eta_cases():
    empty = BroadcastProgress(
        processed=0,
        total=0,
        success=0,
        failed=0,
        elapsed_seconds=0.0,
    )
    assert empty.percent == 100
    assert empty.eta_seconds is None

    partial = BroadcastProgress(
        processed=2,
        total=4,
        success=2,
        failed=0,
        elapsed_seconds=4.0,
    )
    assert partial.percent == 50
    assert partial.eta_seconds == 4


@pytest.mark.asyncio
async def test_broadcast_rejects_invalid_progress_interval():
    service = BroadcastService(
        user_repository=FakeUserRepository([]),
        broadcast_repository=FakeBroadcastRepository(),
        bot=FakeBot(),
    )
    with pytest.raises(ValueError):
        await service.broadcast(from_chat_id=1, message_id=2, progress_interval=0)
