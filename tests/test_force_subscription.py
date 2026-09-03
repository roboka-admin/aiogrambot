from datetime import datetime
from types import SimpleNamespace

import pytest

from models.force_subscription import ForceSubscriptionTarget, ForceSubscriptionTargetType
from models.bot_settings import BotSettings
from repositories.force_subscription import ForceSubscriptionRepository


class FakeResult:
    def __init__(self, record=None, records=None, rowcount=0):
        self._record = record
        self._records = records or []
        self.rowcount = rowcount

    def scalar_one_or_none(self):
        return self._record

    def scalars(self):
        return self

    def all(self):
        return self._records


class FakeSession:
    def __init__(self):
        self.added = []
        self.flushed = 0
        self.result = FakeResult()

    async def execute(self, statement):
        return self.result

    def add(self, record):
        self.added.append(record)

    async def flush(self):
        self.flushed += 1



def test_bot_settings_force_subscription_defaults_to_disabled() -> None:
    settings = BotSettings()

    assert settings.force_subscription_enabled is False


def test_force_subscription_target_has_safe_defaults() -> None:
    target = ForceSubscriptionTarget(
        chat_id=-100123,
        title="Test Channel",
        target_type=ForceSubscriptionTargetType.CHANNEL,
    )

    assert target.is_active is True
    assert target.username is None
    assert target.invite_link is None


@pytest.mark.asyncio
async def test_repository_create_persists_target_and_flushes() -> None:
    session = FakeSession()
    repository = ForceSubscriptionRepository(session)
    now = datetime(2026, 9, 3, 12, 0, 0)
    target = ForceSubscriptionTarget(
        chat_id=-100123,
        title="Test Channel",
        target_type=ForceSubscriptionTargetType.CHANNEL,
        username="test_channel",
        invite_link="https://t.me/test_channel",
        created_at=now,
        updated_at=now,
    )

    created = await repository.create(target)

    assert created == target
    assert len(session.added) == 1
    assert session.added[0].chat_id == -100123
    assert session.added[0].target_type == "channel"
    assert session.flushed == 1


def test_repository_maps_database_record_to_domain() -> None:
    now = datetime(2026, 9, 3, 12, 0, 0)
    record = SimpleNamespace(
        chat_id=-100123,
        title="Test Group",
        target_type="supergroup",
        username="test_group",
        invite_link="https://t.me/+abc",
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    target = ForceSubscriptionRepository._to_domain(record)

    assert target.chat_id == record.chat_id
    assert target.title == record.title
    assert target.target_type is ForceSubscriptionTargetType.SUPERGROUP
    assert target.username == record.username
    assert target.invite_link == record.invite_link
    assert target.is_active is True
    assert target.created_at == now
    assert target.updated_at == now
