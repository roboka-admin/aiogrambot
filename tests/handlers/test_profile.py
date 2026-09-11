from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from callbacks.profile import ProfileCallback
from handlers.profile import (
    cancel_edit_handler,
    edit_name_start_handler,
    profile_handler,
    save_age_handler,
    save_name_handler,
)
from keyboards.profile import profile_edit_keyboard, profile_keyboard
from models.user import RegistrationStatus, User, UserStatus
from services.referral import ReferralRewardProgress


def make_user(**overrides) -> User:
    defaults = dict(
        telegram_id=42,
        telegram_name="Ali TG",
        username="ali_dev",
        name="Ali",
        age=28,
        coins=25,
        warnings=1,
        registration_status=RegistrationStatus.REGISTERED,
        first_seen_at=datetime(2026, 3, 21, 12, 0),
    )
    defaults.update(overrides)
    return User(**defaults)


def make_progress(**overrides) -> ReferralRewardProgress:
    defaults = dict(
        registered_referrals=4,
        total_coins_earned=15,
        invites_until_next_reward=2,
        reward_coins=5,
        reward_per_invites=3,
    )
    defaults.update(overrides)
    return ReferralRewardProgress(**defaults)


def make_referral_service(progress: ReferralRewardProgress | None = None) -> MagicMock:
    service = MagicMock()
    service.get_reward_progress = AsyncMock(return_value=progress or make_progress())
    return service


def make_message(text: str = "") -> MagicMock:
    message = MagicMock()
    message.text = text
    message.answer = AsyncMock()
    return message


def make_callback() -> MagicMock:
    callback = MagicMock()
    callback.message = MagicMock()
    callback.message.text = "old"
    callback.message.reply_markup = None
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    return callback


def make_state() -> MagicMock:
    state = MagicMock()
    state.set_state = AsyncMock()
    state.clear = AsyncMock()
    return state


@pytest.mark.asyncio
async def test_profile_shows_grouped_details_with_inline_actions() -> None:
    message = make_message("👤 پروفایل")
    user = make_user(name="<Ali>")

    await profile_handler(message, user, make_referral_service())

    text = message.answer.await_args.args[0]
    assert "&lt;Ali&gt;" in text and "<Ali>" not in text  # escaped
    assert "@ali_dev" in text
    assert "<code>42</code>" in text
    assert "موجودی: <b>25</b> سکه" in text
    assert "کسب‌شده از دعوت: <b>15</b> سکه" in text
    assert "✅ فعال" in text
    assert "اخطار: <b>1</b> از 3" in text
    assert "عضو از: 1405/01/01" in text
    assert "active" not in text  # no raw enum leak
    assert message.answer.await_args.kwargs["reply_markup"] == profile_keyboard()
    assert message.answer.await_args.kwargs["parse_mode"] == "HTML"


@pytest.mark.asyncio
async def test_profile_omits_username_line_when_missing_and_shows_blocked() -> None:
    message = make_message()
    user = make_user(username=None, status=UserStatus.BLOCKED)

    await profile_handler(message, user, make_referral_service())

    text = message.answer.await_args.args[0]
    assert "نام کاربری" not in text
    assert "🚫 مسدود" in text


@pytest.mark.asyncio
async def test_edit_name_start_edits_in_place_and_sets_state() -> None:
    callback = make_callback()
    state = make_state()

    await edit_name_start_handler(callback, state, make_user())

    state.set_state.assert_awaited_once()
    text = callback.message.edit_text.await_args.args[0]
    assert "نام فعلی: <b>Ali</b>" in text
    assert callback.message.edit_text.await_args.kwargs["reply_markup"] == profile_edit_keyboard()


@pytest.mark.asyncio
async def test_cancel_edit_restores_profile_and_clears_state() -> None:
    callback = make_callback()
    state = make_state()

    await cancel_edit_handler(callback, state, make_user(), make_referral_service())

    state.clear.assert_awaited_once()
    assert callback.message.edit_text.await_args.kwargs["reply_markup"] == profile_keyboard()
    callback.answer.assert_awaited_once_with("انصراف داده شد.")


@pytest.mark.asyncio
async def test_save_name_updates_and_shows_refreshed_profile() -> None:
    message = make_message("  Reza ")
    state = make_state()
    user_service = MagicMock()
    user_service.update_name = AsyncMock(return_value=make_user(name="Reza"))

    await save_name_handler(message, state, make_user(), user_service, make_referral_service())

    user_service.update_name.assert_awaited_once_with(42, "Reza")
    state.clear.assert_awaited_once()
    text = message.answer.await_args.args[0]
    assert text.startswith("✅ نام شما تغییر کرد.")
    assert "نام: <b>Reza</b>" in text
    assert message.answer.await_args.kwargs["reply_markup"] == profile_keyboard()


@pytest.mark.asyncio
async def test_save_name_rejects_invalid_and_keeps_state() -> None:
    message = make_message("1")
    state = make_state()
    user_service = MagicMock()
    user_service.update_name = AsyncMock()

    await save_name_handler(message, state, make_user(), user_service, make_referral_service())

    user_service.update_name.assert_not_awaited()
    state.clear.assert_not_called()
    assert message.answer.await_args.kwargs["reply_markup"] == profile_edit_keyboard()


@pytest.mark.asyncio
async def test_save_age_accepts_persian_digits() -> None:
    message = make_message("۳۰")
    state = make_state()
    user_service = MagicMock()
    user_service.update_age = AsyncMock(return_value=make_user(age=30))

    await save_age_handler(message, state, make_user(), user_service, make_referral_service())

    user_service.update_age.assert_awaited_once_with(42, 30)
    assert "سن: <b>30</b>" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_save_age_rejects_out_of_range() -> None:
    message = make_message("150")
    state = make_state()
    user_service = MagicMock()
    user_service.update_age = AsyncMock()

    await save_age_handler(message, state, make_user(), user_service, make_referral_service())

    user_service.update_age.assert_not_awaited()
    assert message.answer.await_args.args[0].startswith("❌")


def test_profile_callbacks_round_trip() -> None:
    packed = ProfileCallback(action="edit_age").pack()
    assert ProfileCallback.unpack(packed).action == "edit_age"
