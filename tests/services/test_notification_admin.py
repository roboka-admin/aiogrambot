from unittest.mock import AsyncMock, MagicMock

import pytest

from services.notification import NotificationService


@pytest.mark.asyncio
async def test_admin_added_sends_notification_to_new_admin():
    gateway = MagicMock()
    gateway.send_message = AsyncMock()
    service = NotificationService(telegram_gateway=gateway)

    await service.admin_added(200)

    gateway.send_message.assert_awaited_once_with(
        200,
        "🛡 حساب شما به عنوان ادمین ربات فعال شد.",
    )
