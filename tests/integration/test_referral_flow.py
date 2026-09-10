from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from aiogram.filters import CommandObject

from callbacks.referral import ReferralListCallback
from handlers.referral import referral_back_handler, referral_handler, referral_list_handler
from handlers.start import start_handler
from keyboards.referral import referral_keyboard, referral_list_keyboard
from models.user import RegistrationStatus, User
from services.referral import ReferralRewardProgress


@pytest.mark.asyncio
async def test_start_handler_processes_referral_payload_for_new_user():
    user = User(telegram_id=42, telegram_name="New User")
    message = MagicMock()
    message.from_user.first_name = "New"
    message.answer = AsyncMock()
    referral_service = MagicMock()
    referral_service.process_start = AsyncMock(return_value=7)
    referral_service.get_referral_count = AsyncMock(return_value=3)
    referral_service.get_reward_progress = AsyncMock(
        return_value=ReferralRewardProgress(
            registered_referrals=1,
            total_coins_earned=1,
            invites_until_next_reward=1,
            reward_coins=1,
            reward_per_invites=1,
        )
    )
    notification_service = MagicMock()
    notification_service.referral_joined = AsyncMock()

    await start_handler(
        message,
        user,
        CommandObject(command="start", args="ref_owner"),
        referral_service,
        notification_service,
    )

    referral_service.process_start.assert_awaited_once_with(
        telegram_id=42,
        referral_code="ref_owner",
    )
    referral_service.get_referral_count.assert_awaited_once_with(7)
    notification_service.referral_joined.assert_awaited_once_with(7, "New", 3)
    message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_handler_consumes_plain_start_without_referral_payload():
    user = User(telegram_id=42, telegram_name="New User")
    message = MagicMock()
    message.from_user.first_name = "New"
    message.answer = AsyncMock()
    referral_service = MagicMock()
    referral_service.process_start = AsyncMock(return_value=None)
    notification_service = MagicMock()
    notification_service.referral_joined = AsyncMock()

    await start_handler(
        message,
        user,
        CommandObject(command="start"),
        referral_service,
        notification_service,
    )

    referral_service.process_start.assert_awaited_once_with(
        telegram_id=42,
        referral_code=None,
    )
    notification_service.referral_joined.assert_not_awaited()


@pytest.mark.asyncio
async def test_registered_user_does_not_attempt_to_claim_referral():
    user = User(
        telegram_id=42,
        telegram_name="Registered User",
        registration_status=RegistrationStatus.REGISTERED,
    )
    message = MagicMock()
    message.from_user.first_name = "Registered"
    message.answer = AsyncMock()
    referral_service = MagicMock()
    referral_service.process_start = AsyncMock()
    notification_service = MagicMock()
    notification_service.referral_joined = AsyncMock()

    await start_handler(
        message,
        user,
        CommandObject(command="start", args="ref_owner"),
        referral_service,
        notification_service,
    )

    referral_service.process_start.assert_not_awaited()
    notification_service.referral_joined.assert_not_awaited()
    message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_referral_handler_creates_link_and_shows_statistics():
    user = User(telegram_id=42, telegram_name="User")
    message = MagicMock()
    message.answer = AsyncMock()
    referral_service = MagicMock()
    referral_service.ensure_referral_code = AsyncMock(return_value="ref_abc")
    referral_service.get_referral_count = AsyncMock(return_value=7)
    referral_service.get_reward_progress = AsyncMock(
        return_value=ReferralRewardProgress(
            registered_referrals=4,
            total_coins_earned=6,
            invites_until_next_reward=2,
            reward_coins=5,
            reward_per_invites=3,
        )
    )

    with patch(
        "handlers.referral.create_start_link",
        new_callable=AsyncMock,
        return_value="https://t.me/test_bot?start=ref_abc",
    ) as create_link:
        await referral_handler(message, user, referral_service)

    referral_service.ensure_referral_code.assert_awaited_once_with(42)
    referral_service.get_referral_count.assert_awaited_once_with(42)
    create_link.assert_awaited_once_with(message.bot, "ref_abc")
    message.answer.assert_awaited_once()
    text = message.answer.await_args.args[0]
    assert "https://t.me/test_bot?start=ref_abc" in text
    assert "7" in text
    # The link must be copy-friendly (monospace) and the message rendered as HTML.
    assert "<code>https://t.me/test_bot?start=ref_abc</code>" in text
    # Reward rule and progress are surfaced so users know what they earn.
    assert "هر <b>3</b> دعوت ثبت‌نام‌شده = <b>5</b> سکه" in text
    assert "سکه‌های کسب‌شده از دعوت: <b>6</b>" in text
    assert "تا پاداش بعدی: <b>2</b>" in text
    assert message.answer.await_args.kwargs["parse_mode"] == "HTML"


@pytest.mark.asyncio
async def test_referral_share_button_sends_personal_invitation():
    keyboard = referral_keyboard(
        referral_link="https://t.me/test_bot?start=ref_abc",
        has_referrals=True,
    )

    share_button = keyboard.inline_keyboard[0][0]
    assert share_button.url is not None

    parsed = urlparse(share_button.url)
    assert parsed.netloc == "t.me"
    assert parsed.path == "/share/url"
    params = parse_qs(parsed.query)
    assert params["url"] == ["https://t.me/test_bot?start=ref_abc"]
    # The shared message must read as a personal invitation, not a bare link.
    assert params["text"][0].startswith("سلام")


@pytest.mark.asyncio
async def test_referral_list_renders_status_icons_and_escapes_names():
    referred_users = [
        User(
            telegram_id=1,
            telegram_name="<b>hacker</b> & co",
            registration_status=RegistrationStatus.REGISTERED,
        ),
        User(
            telegram_id=2,
            telegram_name="Sara",
            registration_status=RegistrationStatus.UNREGISTERED,
        ),
    ]
    callback = MagicMock()
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.text = "stale screen"
    callback.message.edit_text = AsyncMock()
    referral_service = MagicMock()
    referral_service.get_referrals_page = AsyncMock(
        return_value=(referred_users, 2, 1)
    )

    await referral_list_handler(
        callback,
        ReferralListCallback(page=1),
        User(telegram_id=42, telegram_name="Referrer"),
        referral_service,
    )

    referral_service.get_referrals_page.assert_awaited_once_with(
        telegram_id=42, page=1, page_size=10
    )
    text = callback.message.edit_text.await_args.args[0]
    assert callback.message.edit_text.await_args.kwargs["parse_mode"] == "HTML"
    # User-controlled names must be HTML-escaped.
    assert "&lt;b&gt;hacker&lt;/b&gt; &amp; co" in text
    assert "<b>hacker</b>" not in text
    assert "✅" in text
    assert "⏳" in text
    assert "مجموع: 2" in text
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_referral_back_handler_returns_to_main_screen():
    user = User(telegram_id=42, telegram_name="Referrer")
    callback = MagicMock()
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.text = "referral list screen"
    callback.message.edit_text = AsyncMock()
    referral_service = MagicMock()
    referral_service.ensure_referral_code = AsyncMock(return_value="ref_abc")
    referral_service.get_referral_count = AsyncMock(return_value=3)
    referral_service.get_reward_progress = AsyncMock(
        return_value=ReferralRewardProgress(
            registered_referrals=1,
            total_coins_earned=1,
            invites_until_next_reward=1,
            reward_coins=1,
            reward_per_invites=1,
        )
    )

    with patch(
        "handlers.referral.create_start_link",
        new_callable=AsyncMock,
        return_value="https://t.me/test_bot?start=ref_abc",
    ):
        await referral_back_handler(callback, user, referral_service)

    text = callback.message.edit_text.await_args.args[0]
    assert "<code>https://t.me/test_bot?start=ref_abc</code>" in text
    assert "هر دعوت ثبت‌نام‌شده = <b>1</b> سکه" in text
    assert "3" in text
    assert callback.message.edit_text.await_args.kwargs["parse_mode"] == "HTML"
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_referral_list_keyboard_keeps_pagination_and_offers_back():
    keyboard = referral_list_keyboard(page=2, total_pages=3)

    navigation = keyboard.inline_keyboard[0]
    assert navigation[0].callback_data == ReferralListCallback(page=1).pack()
    assert navigation[1].text == "2/3"
    assert navigation[2].callback_data == ReferralListCallback(page=3).pack()

    back_button = keyboard.inline_keyboard[1][0]
    assert back_button.text == "🔙 بازگشت"
    assert back_button.callback_data == "referral_back"
