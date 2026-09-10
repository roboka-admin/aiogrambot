from unittest.mock import AsyncMock, MagicMock

import pytest

from exceptions.user import UserAlreadyExistsError
from handlers.register import process_age
from keyboards.menu import main_menu
from models.user import RegistrationStatus, User


def make_message(text: str) -> MagicMock:
    message = MagicMock()
    message.text = text
    message.from_user = MagicMock(id=10)
    message.answer = AsyncMock()
    return message


def make_state(name: str = "Sara") -> MagicMock:
    state = MagicMock()
    state.get_data = AsyncMock(return_value={"name": name})
    state.clear = AsyncMock()
    return state


@pytest.mark.asyncio
async def test_successful_registration_shows_main_menu() -> None:
    message = make_message("25")
    state = make_state()
    register_service = MagicMock()
    register_service.register = AsyncMock(
        return_value=User(
            telegram_id=10,
            telegram_name="Sara",
            name="Sara",
            age=25,
            registration_status=RegistrationStatus.REGISTERED,
        )
    )

    await process_age(message, state, register_service)

    register_service.register.assert_awaited_once_with(
        telegram_id=10, name="Sara", age=25
    )
    state.clear.assert_awaited_once()
    message.answer.assert_awaited_once()
    # The user has just unlocked the bot, so the main menu buttons must be
    # attached to the confirmation instead of leaving them without navigation.
    assert message.answer.await_args.kwargs["reply_markup"] is main_menu


@pytest.mark.asyncio
async def test_already_registered_user_does_not_get_menu_from_registration() -> None:
    message = make_message("25")
    state = make_state()
    register_service = MagicMock()
    register_service.register = AsyncMock(side_effect=UserAlreadyExistsError())

    await process_age(message, state, register_service)

    state.clear.assert_awaited_once()
    message.answer.assert_awaited_once_with("❌ شما قبلاً ثبت نام کرده‌اید.")
