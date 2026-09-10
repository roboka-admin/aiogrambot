from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.methods import SendMessage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.telegram import AiogramTelegramGateway, edit_reply_markup_if_changed
from services.telegram import TelegramAccessError, TelegramRateLimitError


def make_retry_after(seconds: int = 3) -> TelegramRetryAfter:
    return TelegramRetryAfter(
        method=SendMessage(chat_id=1, text="test"),
        message="retry",
        retry_after=seconds,
    )


@pytest.mark.asyncio
async def test_gateway_maps_chat_response_to_domain_data() -> None:
    bot = MagicMock()
    bot.get_chat = AsyncMock(
        return_value=MagicMock(
            id=-1001,
            type="channel",
            title="News",
            username="news",
            invite_link=None,
        )
    )

    chat = await AiogramTelegramGateway(bot).get_chat(chat_id="@news")

    assert chat.id == -1001
    assert chat.type == "channel"
    assert chat.title == "News"
    assert chat.username == "news"
    assert chat.invite_link is None


@pytest.mark.asyncio
async def test_gateway_translates_forbidden_error_to_access_error() -> None:
    bot = MagicMock()
    bot.send_message = AsyncMock(
        side_effect=TelegramForbiddenError(method=MagicMock(), message="blocked")
    )

    with pytest.raises(TelegramAccessError):
        await AiogramTelegramGateway(bot).send_message(123, "hello")


@pytest.mark.asyncio
async def test_gateway_translates_retry_after_error() -> None:
    bot = MagicMock()
    bot.copy_message = AsyncMock(side_effect=make_retry_after(7))

    with pytest.raises(TelegramRateLimitError) as exc_info:
        await AiogramTelegramGateway(bot).copy_message(
            chat_id=1,
            from_chat_id=2,
            message_id=3,
        )

    assert exc_info.value.retry_after == 7


@pytest.mark.asyncio
async def test_gateway_translates_member_status_to_plain_string() -> None:
    bot = MagicMock()
    bot.get_chat_member = AsyncMock(return_value=MagicMock(status="administrator"))

    status = await AiogramTelegramGateway(bot).get_chat_member(
        chat_id=-1001,
        user_id=123,
    )

    assert status == "administrator"


def _keyboard(label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=label, callback_data="x")]]
    )


@pytest.mark.asyncio
async def test_edit_reply_markup_skips_api_call_when_markup_is_identical() -> None:
    message = MagicMock()
    message.reply_markup = _keyboard("same")
    message.edit_reply_markup = AsyncMock()

    assert (
        await edit_reply_markup_if_changed(
            message=message, reply_markup=_keyboard("same")
        )
        is False
    )
    message.edit_reply_markup.assert_not_called()


@pytest.mark.asyncio
async def test_edit_reply_markup_edits_when_markup_differs() -> None:
    message = MagicMock()
    message.reply_markup = _keyboard("old")
    message.edit_reply_markup = AsyncMock()

    assert (
        await edit_reply_markup_if_changed(
            message=message, reply_markup=_keyboard("new")
        )
        is True
    )
    message.edit_reply_markup.assert_awaited_once_with(
        reply_markup=_keyboard("new")
    )


@pytest.mark.asyncio
async def test_edit_reply_markup_returns_false_for_missing_message() -> None:
    assert (
        await edit_reply_markup_if_changed(
            message=None, reply_markup=_keyboard("new")
        )
        is False
    )


@pytest.mark.asyncio
async def test_edit_reply_markup_absorbs_not_modified_race() -> None:
    message = MagicMock()
    message.reply_markup = _keyboard("old")
    message.edit_reply_markup = AsyncMock(
        side_effect=TelegramBadRequest(
            method=MagicMock(),
            message="Bad Request: message is not modified",
        )
    )

    assert (
        await edit_reply_markup_if_changed(
            message=message, reply_markup=_keyboard("new")
        )
        is False
    )


@pytest.mark.asyncio
async def test_edit_reply_markup_reraises_unrelated_errors() -> None:
    message = MagicMock()
    message.reply_markup = _keyboard("old")
    message.edit_reply_markup = AsyncMock(
        side_effect=TelegramBadRequest(
            method=MagicMock(),
            message="Bad Request: message to edit not found",
        )
    )

    with pytest.raises(TelegramBadRequest):
        await edit_reply_markup_if_changed(
            message=message, reply_markup=_keyboard("new")
        )
