from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from models.force_subscription import ForceSubscriptionTarget, ForceSubscriptionTargetType
from services.force_subscription import ForceSubscriptionService, MembershipStatus


def target(chat_id: int = -1001) -> ForceSubscriptionTarget:
    return ForceSubscriptionTarget(
        chat_id=chat_id,
        title="Test channel",
        target_type=ForceSubscriptionTargetType.CHANNEL,
        username="test_channel",
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
    bot.get_chat_member = AsyncMock(side_effect=[MagicMock(status="member"), MagicMock(status="left")])
    first = target(-1001)
    second = target(-1002)
    repository = MagicMock()
    repository.list_active = AsyncMock(return_value=[first, second])
    service = ForceSubscriptionService(bot=bot, repository=repository)
    result = await service.check_membership(user_telegram_id=10)
    assert result.is_allowed is False
    assert result.missing_targets == (second,)
    assert bot.get_chat_member.await_count == 2


@pytest.mark.asyncio
async def test_resolve_public_channel_and_add_target() -> None:
    bot = MagicMock()
    bot.get_chat = AsyncMock(return_value=MagicMock(id=-1001, type="channel", title="News", username="news"))
    repository = MagicMock()
    repository.get = AsyncMock(return_value=None)
    repository.create = AsyncMock(side_effect=lambda value: value)
    service = ForceSubscriptionService(bot=bot, repository=repository)

    resolved = await service.resolve_target("@news")
    created = await service.add_target(resolved)

    assert created.chat_id == -1001
    assert created.title == "News"
    assert created.username == "news"
    repository.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_rejects_private_target_without_join_link() -> None:
    bot = MagicMock()
    bot.get_chat = AsyncMock(return_value=MagicMock(id=-1001, type="supergroup", title="Private", username=None, invite_link=None))
    repository = MagicMock()
    service = ForceSubscriptionService(bot=bot, repository=repository)

    with pytest.raises(ValueError, match="لینک"):
        await service.resolve_target("-1001")


@pytest.mark.asyncio
async def test_resolve_rejects_non_channel_or_group() -> None:
    bot = MagicMock()
    bot.get_chat = AsyncMock(return_value=MagicMock(id=10, type="private", title="User", username="user"))
    repository = MagicMock()
    service = ForceSubscriptionService(bot=bot, repository=repository)

    with pytest.raises(ValueError, match="فقط کانال"):
        await service.resolve_target("@user")


@pytest.mark.asyncio
async def test_add_rejects_duplicate_target() -> None:
    repository = MagicMock()
    repository.get = AsyncMock(return_value=target())
    service = ForceSubscriptionService(bot=MagicMock(), repository=repository)

    with pytest.raises(ValueError, match="قبلاً"):
        await service.add_target(target())


@pytest.mark.asyncio
async def test_toggle_target_changes_active_state() -> None:
    existing = target()
    existing.is_active = True
    repository = MagicMock()
    repository.get = AsyncMock(return_value=existing)
    repository.update = AsyncMock(side_effect=lambda value: value)
    service = ForceSubscriptionService(bot=MagicMock(), repository=repository)

    result = await service.toggle_target(existing.chat_id)

    assert result is existing
    assert result.is_active is False
    repository.update.assert_awaited_once_with(existing)


@pytest.mark.asyncio
async def test_delete_target_delegates_to_repository() -> None:
    repository = MagicMock()
    repository.delete = AsyncMock(return_value=True)
    service = ForceSubscriptionService(bot=MagicMock(), repository=repository)

    assert await service.delete_target(-1001) is True
    repository.delete.assert_awaited_once_with(-1001)
