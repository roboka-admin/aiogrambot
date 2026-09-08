from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.filters import CommandObject

from handlers.referral import referral_handler
from handlers.start import start_handler
from models.user import RegistrationStatus, User


@pytest.mark.asyncio
async def test_start_handler_processes_referral_payload_for_new_user():
    user = User(telegram_id=42, telegram_name="New User")
    message = MagicMock()
    message.from_user.first_name = "New"
    message.answer = AsyncMock()
    referral_service = MagicMock()
    referral_service.process_start = AsyncMock(return_value=True)

    await start_handler(
        message,
        user,
        CommandObject(command="start", args="ref_owner"),
        referral_service,
    )

    referral_service.process_start.assert_awaited_once_with(
        telegram_id=42,
        referral_code="ref_owner",
    )
    message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_handler_consumes_plain_start_without_referral_payload():
    user = User(telegram_id=42, telegram_name="New User")
    message = MagicMock()
    message.from_user.first_name = "New"
    message.answer = AsyncMock()
    referral_service = MagicMock()
    referral_service.process_start = AsyncMock(return_value=False)

    await start_handler(
        message,
        user,
        CommandObject(command="start"),
        referral_service,
    )

    referral_service.process_start.assert_awaited_once_with(
        telegram_id=42,
        referral_code=None,
    )


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

    await start_handler(
        message,
        user,
        CommandObject(command="start", args="ref_owner"),
        referral_service,
    )

    referral_service.process_start.assert_not_awaited()
    message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_referral_handler_creates_link_and_shows_statistics():
    user = User(telegram_id=42, telegram_name="User")
    message = MagicMock()
    message.answer = AsyncMock()
    referral_service = MagicMock()
    referral_service.ensure_referral_code = AsyncMock(return_value="ref_abc")
    referral_service.get_referral_count = AsyncMock(return_value=7)

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
