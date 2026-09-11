from unittest.mock import AsyncMock, MagicMock

import pytest

from callbacks.admin import AdminReferralRewardCallback
from handlers.admin_settings import (
    _parse_reward_input,
    _reward_history_text,
    _update_settings_message,
    referral_reward_manual_input_handler,
    referral_reward_preset_handler,
    referral_reward_step_handler,
)
from keyboards.admin_referral_reward import admin_referral_reward_keyboard
from keyboards.admin_settings import admin_settings_keyboard
from models.bot_settings import BotSettings
from models.referral_reward import ReferralRewardEntry, ReferralRewardHistoryItem


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
        "وضعیت مؤثر: 🔴 غیرفعال برای کاربران\n"
        "پاداش دعوت: 1 سکه به ازای هر 1 دعوت ثبت‌نام‌شده\n\n"
        "مدیران حتی در حالت خاموش یا تعمیرات به ربات دسترسی دارند.",
        reply_markup=admin_settings_keyboard(new_settings),
        parse_mode=None,
    )
    callback.answer.assert_awaited_once_with("وضعیت ربات تغییر کرد.")


def test_settings_keyboard_has_toggle_rows_and_referral_reward_row() -> None:
    keyboard = admin_settings_keyboard(BotSettings())

    assert len(keyboard.inline_keyboard) == 3
    assert len(keyboard.inline_keyboard[0]) == 2
    assert len(keyboard.inline_keyboard[1]) == 2
    assert len(keyboard.inline_keyboard[2]) == 1
    assert keyboard.inline_keyboard[2][0].callback_data == (
        AdminReferralRewardCallback(action="open").pack()
    )

    assert [button.callback_data for button in keyboard.inline_keyboard[0]] == [
        "admin_settings_toggle_bot",
        "admin_settings_toggle_maintenance",
    ]
    assert [button.callback_data for button in keyboard.inline_keyboard[1]] == [
        "admin_settings_toggle_antispam",
        "admin_settings_toggle_force_subscription",
    ]


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


def test_settings_keyboard_referral_reward_label_reflects_configuration() -> None:
    keyboard = admin_settings_keyboard(
        BotSettings(referral_reward_coins=5, referral_reward_per_invites=3)
    )

    assert keyboard.inline_keyboard[2][0].text == "🎁 پاداش دعوت: 5 سکه / 3 دعوت"


def _reward_editor_callback() -> MagicMock:
    callback = MagicMock()
    callback.message = MagicMock()
    callback.message.text = "old"
    callback.message.reply_markup = None
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    return callback


def _settings_service(current: BotSettings) -> MagicMock:
    service = MagicMock()
    service.get_settings = AsyncMock(return_value=current)

    async def _set(*, coins: int, per_invites: int) -> BotSettings:
        if coins <= 0 or per_invites <= 0:
            raise ValueError
        return BotSettings(referral_reward_coins=coins, referral_reward_per_invites=per_invites)

    service.set_referral_reward = AsyncMock(side_effect=_set)
    return service


def test_reward_keyboard_hides_minus_at_minimum_and_marks_active_preset() -> None:
    keyboard = admin_referral_reward_keyboard(BotSettings())  # 1 coin / 1 invite

    coins_row, invites_row, presets = keyboard.inline_keyboard[:3]
    assert [button.text for button in coins_row] == ["🪙 1 سکه", "➕"]
    assert [button.text for button in invites_row] == ["👥 هر 1 دعوت", "➕"]
    assert presets[0].text.startswith("✅ ")
    assert not presets[1].text.startswith("✅ ")


def test_reward_keyboard_shows_minus_above_minimum() -> None:
    keyboard = admin_referral_reward_keyboard(
        BotSettings(referral_reward_coins=5, referral_reward_per_invites=3)
    )

    coins_row = keyboard.inline_keyboard[0]
    assert [button.text for button in coins_row] == ["➖", "🪙 5 سکه", "➕"]
    assert coins_row[0].callback_data == AdminReferralRewardCallback(
        action="coins", delta=-1
    ).pack()


@pytest.mark.asyncio
async def test_reward_step_saves_immediately_and_redraws() -> None:
    callback = _reward_editor_callback()
    service = _settings_service(
        BotSettings(referral_reward_coins=2, referral_reward_per_invites=3)
    )

    await referral_reward_step_handler(
        callback, AdminReferralRewardCallback(action="coins", delta=1), service
    )

    service.set_referral_reward.assert_awaited_once_with(coins=3, per_invites=3)
    callback.message.edit_text.assert_awaited_once()
    assert "هر 3 دعوت ثبت‌نام‌شده → 3 سکه" in callback.message.edit_text.await_args.args[0]
    callback.answer.assert_awaited_once_with("ذخیره شد ✅")


@pytest.mark.asyncio
async def test_reward_step_below_minimum_alerts_without_saving_state() -> None:
    callback = _reward_editor_callback()
    service = _settings_service(BotSettings())  # invites already at 1

    await referral_reward_step_handler(
        callback, AdminReferralRewardCallback(action="invites", delta=-1), service
    )

    callback.message.edit_text.assert_not_called()
    callback.answer.assert_awaited_once_with("حداقل مقدار ۱ است.", show_alert=True)


@pytest.mark.asyncio
async def test_reward_preset_applies_both_values() -> None:
    callback = _reward_editor_callback()
    service = _settings_service(BotSettings())

    await referral_reward_preset_handler(
        callback, AdminReferralRewardCallback(action="preset", delta=10, value=5), service
    )

    service.set_referral_reward.assert_awaited_once_with(coins=10, per_invites=5)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("5 3", (5, 3)),
        ("5,3", (5, 3)),
        ("5/3", (5, 3)),
        ("۵ ۳", (5, 3)),
        ("  7   2 ", (7, 2)),
        ("5", None),
        ("5 3 1", None),
        ("0 3", None),
        ("a b", None),
        (None, None),
    ],
)
def test_parse_reward_input(raw, expected) -> None:
    assert _parse_reward_input(raw) == expected


@pytest.mark.asyncio
async def test_manual_input_saves_and_clears_state() -> None:
    message = MagicMock()
    message.text = "۵ ۳"
    message.answer = AsyncMock()
    state = MagicMock()
    state.clear = AsyncMock()
    service = _settings_service(BotSettings())

    await referral_reward_manual_input_handler(message, state, service)

    service.set_referral_reward.assert_awaited_once_with(coins=5, per_invites=3)
    state.clear.assert_awaited_once()
    assert message.answer.await_args.args[0].startswith("✅ ذخیره شد.")


@pytest.mark.asyncio
async def test_manual_input_rejects_bad_format_and_keeps_state() -> None:
    message = MagicMock()
    message.text = "five"
    message.answer = AsyncMock()
    state = MagicMock()
    state.clear = AsyncMock()
    service = _settings_service(BotSettings())

    await referral_reward_manual_input_handler(message, state, service)

    service.set_referral_reward.assert_not_awaited()
    state.clear.assert_not_called()
    assert message.answer.await_args.args[0].startswith("❌")


def test_reward_history_shows_names_and_falls_back_to_id() -> None:
    from datetime import datetime

    entry = ReferralRewardEntry(
        id=1,
        referrer_id=7,
        triggered_by_user_id=42,
        coins=5,
        invites_consumed=3,
        created_at=datetime(2026, 9, 11, 10, 30),
    )
    named = ReferralRewardHistoryItem(entry=entry, referrer_name="Ali", triggered_by_name="Sara")
    orphan = ReferralRewardHistoryItem(entry=entry, referrer_name=None, triggered_by_name=None)

    text = _reward_history_text([named, orphan])

    assert "2026-09-11 10:30 — Ali: 5 سکه (بابت 3 دعوت؛ آخرین: Sara)" in text
    assert "ID: 7: 5 سکه (بابت 3 دعوت؛ آخرین: ID: 42)" in text


def test_reward_history_empty_state() -> None:
    assert "هنوز پاداشی پرداخت نشده است." in _reward_history_text([])
