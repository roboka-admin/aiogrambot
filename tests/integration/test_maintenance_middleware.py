from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Chat, Message, Update, User

from middlewares.maintenance import MaintenanceMiddleware
from models.bot_settings import BotSettings


def _message_update(user_id: int) -> Update:
    user = User(id=user_id, is_bot=False, first_name="Test")
    chat = Chat(id=user_id, type="private")
    message = Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=chat,
        from_user=user,
    )
    return Update(update_id=1, message=message)


def _admin_service(*, active: bool) -> MagicMock:
    service = MagicMock()
    service.is_active_admin = AsyncMock(return_value=active)
    return service


@pytest.mark.asyncio
async def test_maintenance_middleware_allows_enabled_bot() -> None:
    handler = AsyncMock(return_value="handled")
    service = MagicMock()
    service.get_settings = AsyncMock(return_value=BotSettings())
    middleware = MaintenanceMiddleware()
    event = _message_update(100)

    result = await middleware(
        handler,
        event,
        {
            "bot_settings_service": service,
            "admin_service": _admin_service(active=False),
        },
    )

    assert result == "handled"
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_maintenance_middleware_blocks_disabled_bot() -> None:
    handler = AsyncMock()
    settings = BotSettings(bot_enabled=False)
    service = MagicMock()
    service.get_settings = AsyncMock(return_value=settings)
    middleware = MaintenanceMiddleware()
    middleware._notify_blocked = AsyncMock()
    event = _message_update(100)

    result = await middleware(
        handler,
        event,
        {
            "bot_settings_service": service,
            "admin_service": _admin_service(active=False),
        },
    )

    assert result is None
    handler.assert_not_awaited()
    middleware._notify_blocked.assert_awaited_once_with(
        event,
        settings.offline_message,
    )


@pytest.mark.asyncio
async def test_maintenance_middleware_blocks_maintenance_mode() -> None:
    handler = AsyncMock()
    settings = BotSettings(bot_enabled=True, maintenance_mode=True)
    service = MagicMock()
    service.get_settings = AsyncMock(return_value=settings)
    middleware = MaintenanceMiddleware()
    middleware._notify_blocked = AsyncMock()
    event = _message_update(100)

    result = await middleware(
        handler,
        event,
        {
            "bot_settings_service": service,
            "admin_service": _admin_service(active=False),
        },
    )

    assert result is None
    handler.assert_not_awaited()
    middleware._notify_blocked.assert_awaited_once_with(
        event,
        settings.maintenance_message,
    )


@pytest.mark.asyncio
async def test_maintenance_middleware_always_allows_active_database_admin() -> None:
    handler = AsyncMock(return_value="handled")
    service = MagicMock()
    service.get_settings = AsyncMock()
    admin_service = _admin_service(active=True)
    middleware = MaintenanceMiddleware()
    event = _message_update(999)

    result = await middleware(
        handler,
        event,
        {
            "bot_settings_service": service,
            "admin_service": admin_service,
        },
    )

    assert result == "handled"
    handler.assert_awaited_once()
    service.get_settings.assert_not_awaited()
    admin_service.is_active_admin.assert_awaited_once_with(999)
