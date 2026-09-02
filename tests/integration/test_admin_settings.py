from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import InlineKeyboardMarkup

from handlers.admin_settings import _update_settings_message
from keyboards.admin_settings import admin_settings_keyboard
from models.bot_settings import BotSettings


@pytest.mark.asyncio
async def test_settings_refresh_skips_unchanged_telegram_message() -> None:
    settings = BotSettings()
    message = MagicMock()
    message.text = (
        "⚙️ تنظیمات ربات\n\n"
        "وضعیت اصلی: 🟢 روشن\n"
        "حالت تعمیرات: ⚪ غیرفعال\n"
        "وضعیت مؤثر: 🟢 در دسترس کاربران\n\n"
        "مدیران حتی در حالت خاموش یا تعمیرات به ربات دسترسی دارند."
    )
    message.reply_markup = admin_settings_keyboard(settings)
    message.edit_text = AsyncMock()

    callback = MagicMock()
    callback.message = message
    callback.answer = AsyncMock()

    await _update_settings_message(callback, settings, "بروزرسانی شد.")

    message.edit_text.assert_not_awaited()
    callback.answer.assert_awaited_once_with("بروزرسانی شد.")


@pytest.mark.asyncio
async def test_settings_refresh_edits_when_message_is_stale() -> None:
    current_settings = BotSettings()
    new_settings = BotSettings(bot_enabled=False)
    message = MagicMock()
    message.text = "old text"
    message.reply_markup = admin_settings_keyboard(current_settings)
    message.edit_text = AsyncMock()

    callback = MagicMock()
    callback.message = message
    callback.answer = AsyncMock()

    await _update_settings_message(callback, new_settings, "بروزرسانی شد.")

    message.edit_text.assert_awaited_once_with(
        "⚙️ تنظیمات ربات\n\n"
        "وضعیت اصلی: 🔴 خاموش\n"
        "حالت تعمیرات: ⚪ غیرفعال\n"
        "وضعیت مؤثر: 🔴 غیرفعال برای کاربران\n\n"
        "مدیران حتی در حالت خاموش یا تعمیرات به ربات دسترسی دارند.",
        reply_markup=admin_settings_keyboard(new_settings),
    )
    callback.answer.assert_awaited_once_with("بروزرسانی شد.")


def test_settings_keyboard_has_expected_two_row_layout() -> None:
    keyboard = admin_settings_keyboard(BotSettings())

    assert len(keyboard.inline_keyboard) == 2
    assert len(keyboard.inline_keyboard[0]) == 2
    assert len(keyboard.inline_keyboard[1]) == 1

    assert [button.callback_data for button in keyboard.inline_keyboard[0]] == [
        "admin_settings_toggle_bot",
        "admin_settings_toggle_maintenance",
    ]
    assert keyboard.inline_keyboard[1][0].callback_data == "admin_settings_refresh"
