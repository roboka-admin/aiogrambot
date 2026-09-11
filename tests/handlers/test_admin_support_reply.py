from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import ReplyKeyboardRemove

from callbacks.admin_support import AdminSupportActionCallback
from handlers.admin_support import close_after_reply_handler, send_support_reply_handler
from keyboards.admin_support import support_reply_sent_keyboard


@pytest.mark.asyncio
async def test_reply_confirmation_offers_inline_close_button() -> None:
    message = MagicMock()
    message.answer = AsyncMock()
    message.copy_to = AsyncMock()
    state = MagicMock()
    state.get_data = AsyncMock(return_value={"telegram_id": 555})
    state.clear = AsyncMock()
    bot = MagicMock()
    bot.send_message = AsyncMock()

    await send_support_reply_handler(message, state, bot)

    state.clear.assert_awaited_once()
    calls = message.answer.await_args_list
    assert calls[0].args[0] == "✅ پاسخ با موفقیت برای کاربر ارسال شد."
    assert isinstance(calls[0].kwargs["reply_markup"], ReplyKeyboardRemove)
    assert calls[1].kwargs["reply_markup"] == support_reply_sent_keyboard(telegram_id=555)
    button = calls[1].kwargs["reply_markup"].inline_keyboard[0][0]
    assert button.text == "🔒 بستن گفتگو"
    unpacked = AdminSupportActionCallback.unpack(button.callback_data)
    assert (unpacked.action, unpacked.telegram_id) == ("close_after_reply", 555)


@pytest.mark.asyncio
async def test_close_after_reply_closes_conversation_and_collapses_prompt() -> None:
    callback = MagicMock()
    callback.message = MagicMock()
    callback.message.text = "می‌خواهید این گفتگو را ببندید؟"
    callback.message.reply_markup = support_reply_sent_keyboard(telegram_id=555)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    support_service = MagicMock()
    support_service.close_user_conversation = AsyncMock(return_value=1)

    await close_after_reply_handler(
        callback,
        AdminSupportActionCallback(
            action="close_after_reply", telegram_id=555, status="open", page=0
        ),
        support_service,
    )

    support_service.close_user_conversation.assert_awaited_once_with(555)
    callback.message.edit_text.assert_awaited_once_with(
        "🔒 گفتگو بسته شد.", reply_markup=None, parse_mode=None
    )
    callback.answer.assert_awaited_once_with("گفتگو بسته شد.")
