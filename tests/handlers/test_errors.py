import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import ErrorEvent

from handlers.errors import handle_error


@pytest.mark.asyncio
async def test_global_error_handler_logs_exception_and_notifies_user(caplog) -> None:
    message = MagicMock()
    message.answer = AsyncMock()
    update = MagicMock(message=message, callback_query=None)
    event = ErrorEvent(update=update, exception=RuntimeError("database exploded"))

    with caplog.at_level(logging.ERROR):
        await handle_error(event)

    message.answer.assert_awaited_once_with(
        "❌ خطایی غیرمنتظره رخ داد. لطفاً دوباره تلاش کنید."
    )
    assert "Unhandled exception while processing update" in caplog.text
    assert "database exploded" in caplog.text


@pytest.mark.asyncio
async def test_global_error_handler_uses_callback_message_when_update_has_no_message() -> None:
    callback_message = MagicMock()
    callback_message.answer = AsyncMock()
    callback_query = MagicMock(message=callback_message)
    update = MagicMock(message=None, callback_query=callback_query)
    event = ErrorEvent(update=update, exception=RuntimeError("boom"))

    await handle_error(event)

    callback_message.answer.assert_awaited_once_with(
        "❌ خطایی غیرمنتظره رخ داد. لطفاً دوباره تلاش کنید."
    )


@pytest.mark.asyncio
async def test_global_error_handler_does_not_fail_when_update_has_no_user_message() -> None:
    update = MagicMock(message=None, callback_query=None)
    event = ErrorEvent(update=update, exception=RuntimeError("boom"))

    await handle_error(event)
