from contextlib import asynccontextmanager

import pytest

from models.force_subscription import ForceSubscriptionTarget, ForceSubscriptionTargetType
from services.force_subscription import ForceSubscriptionService


class RecordingTransactionManager:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    @asynccontextmanager
    async def transaction(self):
        self.events.append("db:begin")
        try:
            yield
        finally:
            self.events.append("db:end")


class FakeRepository:
    async def list_active(self):
        return [
            ForceSubscriptionTarget(
                chat_id=-1001,
                title="Test Channel",
                target_type=ForceSubscriptionTargetType.CHANNEL,
                username="test_channel",
            )
        ]


class FakeTelegramGateway:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def get_chat_member(self, *, chat_id: int, user_id: int) -> str:
        self.events.append("telegram:check")
        return "member"


@pytest.mark.asyncio
async def test_membership_telegram_checks_happen_after_target_transaction_closes():
    events: list[str] = []
    service = ForceSubscriptionService(
        telegram_gateway=FakeTelegramGateway(events),
        repository=FakeRepository(),
        transaction_manager=RecordingTransactionManager(events),
    )

    result = await service.check_membership(user_telegram_id=10)

    assert result.is_allowed is True
    assert events == ["db:begin", "db:end", "telegram:check"]
