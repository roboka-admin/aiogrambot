import pytest
from aiogram.exceptions import TelegramAPIError

from services.notification import NotificationService


class FakeBot:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.messages: list[tuple[int, str]] = []

    async def send_message(self, telegram_id: int, text: str) -> None:
        if self.error:
            raise self.error
        self.messages.append((telegram_id, text))


@pytest.mark.asyncio
async def test_warning_notification_contains_warning_count():
    bot = FakeBot()
    service = NotificationService(bot=bot)
    await service.warning_added(123, 2)
    assert bot.messages == [(123, "⚠️ یک اخطار توسط مدیریت برای شما ثبت شد.\nتعداد اخطار فعلی: 2 از 3")]


@pytest.mark.asyncio
async def test_block_notification_is_sent():
    bot = FakeBot()
    service = NotificationService(bot=bot)
    await service.user_auto_blocked(123)
    assert bot.messages[0][0] == 123
    assert "مسدود شد" in bot.messages[0][1]


@pytest.mark.asyncio
async def test_notification_delivery_error_does_not_escape():
    bot = FakeBot(error=TelegramAPIError(method="sendMessage"))
    service = NotificationService(bot=bot)
    await service.user_blocked(123)
    assert bot.messages == []
