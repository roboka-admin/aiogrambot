from unittest.mock import AsyncMock, MagicMock

import pytest

from models.force_subscription import ForceSubscriptionTarget, ForceSubscriptionTargetType
from services.force_subscription import ForceSubscriptionService


def target(chat_id: int = -1001) -> ForceSubscriptionTarget:
    return ForceSubscriptionTarget(
        chat_id=chat_id,
        title="Test Channel",
        target_type=ForceSubscriptionTargetType.CHANNEL,
        username="test_channel",
    )


@pytest.mark.asyncio
async def test_successful_membership_check_can_be_recorded() -> None:
    bot = MagicMock()
    bot.get_chat_member = AsyncMock(return_value=MagicMock(status="member"))
    repository = MagicMock()
    repository.list_active = AsyncMock(return_value=[target()])
    event_repository = MagicMock()
    event_repository.create = AsyncMock()

    service = ForceSubscriptionService(
        bot=bot,
        repository=repository,
        event_repository=event_repository,
    )

    result = await service.check_membership(user_telegram_id=10)
    await service.record_successful_membership_check(
        user_telegram_id=10,
        result=result,
    )

    assert result.is_allowed is True
    event_repository.create.assert_awaited_once()
    event = event_repository.create.await_args.args[0]
    assert event.user_telegram_id == 10
    assert event.target_chat_id == -1001


@pytest.mark.asyncio
async def test_unsatisfied_membership_is_not_recorded() -> None:
    bot = MagicMock()
    bot.get_chat_member = AsyncMock(return_value=MagicMock(status="left"))
    repository = MagicMock()
    repository.list_active = AsyncMock(return_value=[target()])
    event_repository = MagicMock()
    event_repository.create = AsyncMock()

    service = ForceSubscriptionService(
        bot=bot,
        repository=repository,
        event_repository=event_repository,
    )

    result = await service.check_membership(user_telegram_id=10)
    await service.record_successful_membership_check(
        user_telegram_id=10,
        result=result,
    )

    assert result.is_allowed is False
    event_repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_membership_statistics_use_expected_period_boundaries() -> None:
    bot = MagicMock()
    repository = MagicMock()
    event_repository = MagicMock()
    event_repository.count_total = AsyncMock(return_value=100)
    event_repository.count_since = AsyncMock(side_effect=[10, 40, 80])

    service = ForceSubscriptionService(
        bot=bot,
        repository=repository,
        event_repository=event_repository,
    )

    stats = await service.get_membership_statistics()

    assert stats == {"total": 100, "today": 10, "last_7_days": 40, "last_30_days": 80}
    assert event_repository.count_since.await_count == 3
