from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from models.force_subscription import ForceSubscriptionTarget, ForceSubscriptionTargetType
from services.force_subscription import (
    ForceSubscriptionService,
    MembershipStatus,
)


def target(chat_id: int = -1001) -> ForceSubscriptionTarget:
    return ForceSubscriptionTarget(
        chat_id=chat_id,
        title="Test channel",
        target_type=ForceSubscriptionTargetType.CHANNEL,
    )


@pytest.mark.asyncio
async def test_no_active_targets_allows_user() -> None:
    repository = MagicMock()
    repository.list_active = AsyncMock(return_value=[])
    service = ForceSubscriptionService(bot=MagicMock(), repository=repository)

    result = await service.check_membership(user_telegram_id=10)

    assert result.is_allowed is True
    assert result.targets == ()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["member", "administrator", "creator"])
async def test_member_statuses_are_satisfied(status: str) -> None:
    bot = MagicMock()
    bot.get_chat_member = AsyncMock(return_value=MagicMock(status=status))
    repository = MagicMock()
    repository.list_active = AsyncMock(return_value=[target()])
    service = ForceSubscriptionService(bot=bot, repository=repository)

    result = await service.check_membership(user_telegram_id=10)

    assert result.is_allowed is True
    assert result.targets[0].status is MembershipStatus(status)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["left", "kicked", "restricted", "unknown"])
async def test_unsatisfied_status_blocks_user(status: str) -> None:
    bot = MagicMock()
    bot.get_chat_member = AsyncMock(return_value=MagicMock(status=status))
    repository = MagicMock()
    repository.list_active = AsyncMock(return_value=[target()])
    service = ForceSubscriptionService(bot=bot, repository=repository)

    result = await service.check_membership(user_telegram_id=10)

    assert result.is_allowed is False
    assert len(result.missing_targets) == 1


@pytest.mark.asyncio
async def test_api_error_is_treated_as_unsatisfied() -> None:
    bot = MagicMock()
    bot.get_chat_member = AsyncMock(side_effect=TelegramBadRequest(method=MagicMock(), message="chat not found"))
    repository = MagicMock()
    repository.list_active = AsyncMock(return_value=[target()])
    service = ForceSubscriptionService(bot=bot, repository=repository)

    result = await service.check_membership(user_telegram_id=10)

    assert result.is_allowed is False
    assert result.targets[0].status is MembershipStatus.ERROR


@pytest.mark.asyncio
async def test_forbidden_error_is_treated_as_unsatisfied() -> None:
    bot = MagicMock()
    bot.get_chat_member = AsyncMock(side_effect=TelegramForbiddenError(method=MagicMock(), message="forbidden"))
    repository = MagicMock()
    repository.list_active = AsyncMock(return_value=[target()])
    service = ForceSubscriptionService(bot=bot, repository=repository)

    result = await service.check_membership(user_telegram_id=10)

    assert result.is_allowed is False
    assert result.targets[0].status is MembershipStatus.ERROR


@pytest.mark.asyncio
async def test_multiple_targets_require_all_memberships() -> None:
    bot = MagicMock()
    bot.get_chat_member = AsyncMock(
        side_effect=[MagicMock(status="member"), MagicMock(status="left")]
    )
    first = target(-1001)
    second = target(-1002)
    repository = MagicMock()
    repository.list_active = AsyncMock(return_value=[first, second])
    service = ForceSubscriptionService(bot=bot, repository=repository)

    result = await service.check_membership(user_telegram_id=10)

    assert result.is_allowed is False
    assert result.missing_targets == (second,)
    assert bot.get_chat_member.await_count == 2
