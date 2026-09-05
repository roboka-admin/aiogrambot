from collections.abc import Awaitable, Callable

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message


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
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise
        return False

    return True
