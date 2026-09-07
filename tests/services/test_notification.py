import pytest

from services.notification import NotificationService
from services.telegram import TelegramGatewayError


class FakeTelegramGateway:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.messages: list[tuple[int, str]] = []

    async def send_message(self, telegram_id: int, text: str) -> None:
        if self.error:
            raise self.error
        self.messages.append((telegram_id, text))


@pytest.mark.asyncio
async def test_warning_notification_contains_warning_count():
    gateway = FakeTelegramGateway()
    service = NotificationService(telegram_gateway=gateway)
    await service.warning_added(123, 2)
    assert gateway.messages == [(123, "⚠️ یک اخطار توسط مدیریت برای شما ثبت شد.\nتعداد اخطار فعلی: 2 از 3")]


@pytest.mark.asyncio
async def test_block_notification_is_sent():
    gateway = FakeTelegramGateway()
    service = NotificationService(telegram_gateway=gateway)
    await service.user_auto_blocked(123)
    assert gateway.messages[0][0] == 123
    assert "مسدود شد" in gateway.messages[0][1]


@pytest.mark.asyncio
async def test_admin_added_notification_is_sent():
    gateway = FakeTelegramGateway()
    service = NotificationService(telegram_gateway=gateway)

    await service.admin_added(200)

    assert gateway.messages == [
        (200, "🛡 حساب شما به عنوان ادمین ربات فعال شد."),
    ]


@pytest.mark.asyncio
async def test_notification_delivery_error_does_not_escape():
    gateway = FakeTelegramGateway(error=TelegramGatewayError("send failed"))
    service = NotificationService(telegram_gateway=gateway)
    await service.user_blocked(123)
    assert gateway.messages == []
