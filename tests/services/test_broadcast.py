import asyncio

from services.broadcast import BroadcastProgress, BroadcastService


class FakeUserRepository:
    def __init__(self, ids: list[int]) -> None:
        self.ids = ids

    async def list_active_telegram_ids(self, *, registered_only: bool = False) -> list[int]:
        return list(self.ids)


class FakeBroadcastRepository:
    def __init__(self) -> None:
        self.records = []

    async def create(self, record):
        self.records.append(record)
        return record


class FakeBot:
    def __init__(self, failures: dict[int, Exception] | None = None) -> None:
        self.failures = failures or {}
        self.sent: list[int] = []

    async def copy_message(self, *, chat_id: int, from_chat_id: int, message_id: int) -> None:
        error = self.failures.get(chat_id)
        if error:
            raise error
        self.sent.append(chat_id)


def test_broadcast_empty_recipient_list():
    async def scenario() -> None:
        repository = FakeBroadcastRepository()
        bot = FakeBot()
        service = BroadcastService(
            user_repository=FakeUserRepository([]),
            broadcast_repository=repository,
            bot=bot,
        )

        result = await service.broadcast(from_chat_id=1, message_id=2)

        assert result.total == 0
        assert result.success == 0
        assert result.failed == 0
        assert len(repository.records) == 1

    asyncio.run(scenario())


def test_broadcast_counts_success_and_failure():
    async def scenario() -> None:
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

    asyncio.run(scenario())


def test_broadcast_progress_reports_at_interval_and_completion():
    async def scenario() -> None:
        repository = FakeBroadcastRepository()
        bot = FakeBot()
        service = BroadcastService(
            user_repository=FakeUserRepository([1, 2, 3]),
            broadcast_repository=repository,
            bot=bot,
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

    asyncio.run(scenario())


def test_broadcast_rejects_invalid_progress_interval():
    async def scenario() -> None:
        service = BroadcastService(
            user_repository=FakeUserRepository([]),
            broadcast_repository=FakeBroadcastRepository(),
            bot=FakeBot(),
        )

        try:
            await service.broadcast(from_chat_id=1, message_id=2, progress_interval=0)
        except ValueError:
            pass
        else:
            raise AssertionError("Expected ValueError")

    asyncio.run(scenario())
