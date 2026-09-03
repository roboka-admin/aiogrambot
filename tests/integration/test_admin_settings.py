from unittest.mock import AsyncMock, MagicMock

import pytest

from handlers.admin_settings import _update_settings_message
from keyboards.admin_settings import admin_settings_keyboard
from models.bot_settings import BotSettings


@pytest.mark.asyncio
async def test_settings_update_edits_when_message_is_stale() -> None:
    current_settings = BotSettings()
    new_settings = BotSettings(bot_enabled=False)
    message = MagicMock()
    message.text = "old text"
    message.reply_markup = admin_settings_keyboard(current_settings)
    message.edit_text = AsyncMock()

    callback = MagicMock()
    callback.message = message
    callback.answer = AsyncMock()

    await _update_settings_message(callback, new_settings, "وضعیت ربات تغییر کرد.")

    message.edit_text.assert_awaited_once_with(
        "⚙️ تنظیمات ربات\n\n"
        "وضعیت اصلی: 🔴 خاموش\n"
        "حالت تعمیرات: ⚪ غیرفعال\n"
        "ضد اسپم: 🟢 فعال\n"
        "عضویت اجباری: ⚪ خاموش\n"
        "وضعیت مؤثر: 🔴 غیرفعال برای کاربران\n\n"
        "مدیران حتی در حالت خاموش یا تعمیرات به ربات دسترسی دارند.",
        reply_markup=admin_settings_keyboard(new_settings),
    )
    callback.answer.assert_awaited_once_with("وضعیت ربات تغییر کرد.")


def test_settings_keyboard_has_three_row_layout() -> None:
    keyboard = admin_settings_keyboard(BotSettings())

    assert len(keyboard.inline_keyboard) == 3
    assert len(keyboard.inline_keyboard[0]) == 2
    assert len(keyboard.inline_keyboard[1]) == 2
    assert len(keyboard.inline_keyboard[2]) == 1

    assert [button.callback_data for button in keyboard.inline_keyboard[0]] == [
        "admin_settings_toggle_bot",
        "admin_settings_toggle_maintenance",
    ]
    assert [button.callback_data for button in keyboard.inline_keyboard[1]] == [
        "admin_settings_toggle_antispam",
        "admin_settings_toggle_force_subscription",
    ]
    assert keyboard.inline_keyboard[2][0].callback_data == "admin_force_subscription_manage"


def test_settings_keyboard_antispam_and_force_subscription_labels_reflect_state() -> None:
    enabled = admin_settings_keyboard(
        BotSettings(antispam_enabled=True, force_subscription_enabled=True)
    )
    disabled = admin_settings_keyboard(
        BotSettings(antispam_enabled=False, force_subscription_enabled=False)
    )

    assert enabled.inline_keyboard[1][0].text == "🟢 ضد اسپم فعال"
    assert enabled.inline_keyboard[1][1].text == "🟢 عضویت اجباری فعال"
    assert disabled.inline_keyboard[1][0].text == "🔴 ضد اسپم خاموش"
    assert disabled.inline_keyboard[1][1].text == "⚪ عضویت اجباری خاموش"
