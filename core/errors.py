import logging
from typing import cast

from aiogram.types import ErrorEvent, Message


logger = logging.getLogger(__name__)

ERROR_MESSAGE = "❌ خطایی غیرمنتظره رخ داد. لطفاً دوباره تلاش کنید."


async def handle_error(event: ErrorEvent) -> None:
    """Log an unhandled update exception and show a safe fallback to the user."""
    exception = event.exception
    logger.error(
        "Unhandled exception while processing update",
        exc_info=(type(exception), exception, exception.__traceback__),
    )

    message = _get_message(event)
    if message is None:
        return

    try:
        await message.answer(ERROR_MESSAGE)
    except Exception:
        logger.exception("Failed to send global error response")


def _get_message(event: ErrorEvent) -> Message | None:
    update = event.update
    if update.message is not None:
        return update.message

    if update.callback_query is not None:
        message = update.callback_query.message
        if message is not None and callable(getattr(message, "answer", None)):
            return cast(Message, message)

    return None
