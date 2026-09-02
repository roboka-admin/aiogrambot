from unittest.mock import AsyncMock

import pytest
from aiogram import Bot, Dispatcher

from handlers.start import router as start_router
from middlewares.user import UserMiddleware
from models.user import User


@pytest.mark.asyncio
async def test_start_flow_routes_through_user_middleware_and_injects_user():
    user = User(
        telegram_id=42,
        telegram_name="Test User",
        username="test_user",
    )

    user_service = AsyncMock()
    user_service.get_or_create_telegram_user.return_value = user

    bot = Bot("42:TEST")
    bot.send_message = AsyncMock()

    dp = Dispatcher()
    dp.message.outer_middleware(UserMiddleware())
    dp.include_router(start_router)

    update = {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "date": 1,
            "text": "/start",
            "chat": {"id": 42, "type": "private"},
            "from": {"id": 42, "is_bot": False, "first_name": "Test"},
        },
    }

    await dp.feed_raw_update(
        bot=bot,
        update=update,
        user_service=user_service,
    )

    user_service.get_or_create_telegram_user.assert_awaited_once_with(
        telegram_id=42,
        telegram_name="Test",
        username=None,
    )
    bot.send_message.assert_awaited_once()
    assert "برای شروع ثبت نام کنید" in bot.send_message.await_args.kwargs["text"]
