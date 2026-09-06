from aiogram import Bot
from aiogram.exceptions import (
    AiogramError,
    TelegramForbiddenError,
    TelegramNotFound,
    TelegramRetryAfter,
)
from aiogram.types import InlineKeyboardMarkup, Message

from services.telegram import TelegramAccessError, TelegramChat, TelegramGatewayError, TelegramRateLimitError


class AiogramTelegramGateway:
    """Translate aiogram's Telegram API into the service-layer gateway contract."""

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def copy_message(
        self,
        *,
        chat_id: int,
        from_chat_id: int,
        message_id: int,
    ) -> None:
        try:
            await self._bot.copy_message(
                chat_id=chat_id,
                from_chat_id=from_chat_id,
                message_id=message_id,
            )
        except TelegramRetryAfter as exc:
            raise TelegramRateLimitError(exc.retry_after) from exc
        except (TelegramForbiddenError, TelegramNotFound) as exc:
            raise TelegramAccessError(str(exc)) from exc
        except AiogramError as exc:
            raise TelegramGatewayError(str(exc)) from exc

    async def get_chat(self, *, chat_id: int | str) -> TelegramChat:
        try:
            chat = await self._bot.get_chat(chat_id=chat_id)
        except TelegramRetryAfter as exc:
            raise TelegramRateLimitError(exc.retry_after) from exc
        except (TelegramForbiddenError, TelegramNotFound) as exc:
            raise TelegramAccessError(str(exc)) from exc
        except AiogramError as exc:
            raise TelegramGatewayError(str(exc)) from exc

        return TelegramChat(
            id=chat.id,
            type=chat.type,
            title=chat.title,
            username=chat.username,
            invite_link=chat.invite_link,
        )

    async def get_chat_member(self, *, chat_id: int, user_id: int) -> str:
        try:
            member = await self._bot.get_chat_member(
                chat_id=chat_id,
                user_id=user_id,
            )
        except TelegramRetryAfter as exc:
            raise TelegramRateLimitError(exc.retry_after) from exc
        except (TelegramForbiddenError, TelegramNotFound) as exc:
            raise TelegramAccessError(str(exc)) from exc
        except AiogramError as exc:
            raise TelegramGatewayError(str(exc)) from exc

        return member.status

    async def send_message(self, telegram_id: int, text: str) -> None:
        try:
            await self._bot.send_message(telegram_id, text)
        except TelegramRetryAfter as exc:
            raise TelegramRateLimitError(exc.retry_after) from exc
        except (TelegramForbiddenError, TelegramNotFound) as exc:
            raise TelegramAccessError(str(exc)) from exc
        except AiogramError as exc:
            raise TelegramGatewayError(str(exc)) from exc


async def edit_message_if_changed(
    *,
    message: Message | None,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    """Edit a Telegram message only when its content or markup has changed.

    Returns True when an edit was performed and False when no edit was needed.
    A narrow guard handles the race where Telegram reports that the message
    became identical between our local comparison and the API request.
    """
    if message is None:
        return False

    if message.text == text and message.reply_markup == reply_markup:
        return False

    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except AiogramError as exc:
        if "message is not modified" not in str(exc).lower():
            raise
        return False

    return True
