from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Update

from keyboards.force_subscription import CHECK_CALLBACK
from middlewares.force_subscription import ForceSubscriptionMiddleware
from models.bot_settings import BotSettings
from services.force_subscription import MembershipCheckResult


@pytest.mark.asyncio
async def test_disabled_feature_passes_to_handler() -> None:
    middleware = ForceSubscriptionMiddleware()
    handler = AsyncMock(return_value="handled")
    event = MagicMock(spec=Update)
    user = MagicMock(id=10)
    data = {
        "event_from_user": user,
        "bot_settings_service": MagicMock(
            get_settings=AsyncMock(return_value=BotSettings(force_subscription_enabled=False))
        ),
        "force_subscription_service": MagicMock(),
    }

    result = await middleware(handler, event, data)

    assert result == "handled"
    handler.assert_awaited_once_with(event, data)
    data["force_subscription_service"].check_membership.assert_not_called()


@pytest.mark.asyncio
async def test_admin_bypasses_force_subscription() -> None:
    middleware = ForceSubscriptionMiddleware()
    handler = AsyncMock(return_value="handled")
    event = MagicMock(spec=Update)
    data = {"event_from_user": MagicMock(id=1)}

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("middlewares.force_subscription.ADMIN_IDS", {1})
        result = await middleware(handler, event, data)

    assert result == "handled"
    handler.assert_awaited_once_with(event, data)


@pytest.mark.asyncio
async def test_membership_check_callback_reaches_dedicated_handler() -> None:
    middleware = ForceSubscriptionMiddleware()
    handler = AsyncMock(return_value="handled")
    event = MagicMock(spec=Update)
    event.callback_query = MagicMock(data=CHECK_CALLBACK)
    data = {"event_from_user": MagicMock(id=10)}

    result = await middleware(handler, event, data)

    assert result == "handled"
    handler.assert_awaited_once_with(event, data)


@pytest.mark.asyncio
async def test_satisfied_user_reaches_handler() -> None:
    middleware = ForceSubscriptionMiddleware()
    handler = AsyncMock(return_value="handled")
    event = MagicMock(spec=Update)
    user = MagicMock(id=10)
    settings_service = MagicMock()
    settings_service.get_settings = AsyncMock(
        return_value=BotSettings(force_subscription_enabled=True)
    )
    force_service = MagicMock()
    force_service.check_membership = AsyncMock(
        return_value=MembershipCheckResult(is_allowed=True, targets=())
    )
    data = {
        "event_from_user": user,
        "bot_settings_service": settings_service,
        "force_subscription_service": force_service,
    }

    result = await middleware(handler, event, data)

    assert result == "handled"
    handler.assert_awaited_once_with(event, data)


@pytest.mark.asyncio
async def test_unsatisfied_user_is_blocked_with_subscription_keyboard() -> None:
    middleware = ForceSubscriptionMiddleware()
    handler = AsyncMock(return_value="handled")
    event = MagicMock(spec=Update)
    event.message = MagicMock()
    event.message.answer = AsyncMock()
    event.callback_query = None
    user = MagicMock(id=10)
    settings_service = MagicMock()
    settings_service.get_settings = AsyncMock(
        return_value=BotSettings(force_subscription_enabled=True)
    )
    force_service = MagicMock()
    check_result = MembershipCheckResult(is_allowed=False, targets=())
    force_service.check_membership = AsyncMock(return_value=check_result)
    data = {
        "event_from_user": user,
        "bot_settings_service": settings_service,
        "force_subscription_service": force_service,
    }

    result = await middleware(handler, event, data)

    assert result is None
    handler.assert_not_awaited()
    assert data["force_subscription_result"] is check_result
    event.message.answer.assert_awaited_once()
    _, kwargs = event.message.answer.await_args
    assert kwargs["reply_markup"].inline_keyboard[-1][0].callback_data == CHECK_CALLBACK
