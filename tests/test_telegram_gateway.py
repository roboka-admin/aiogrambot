from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.methods import SendMessage

from core.telegram import AiogramTelegramGateway
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
