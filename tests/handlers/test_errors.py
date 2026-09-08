import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import CallbackQuery, Chat, ErrorEvent, Message, Update, User

from core.errors import handle_error


def _message() -> Message:
    return Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=Chat(id=123, type="private"),
        from_user=User(id=456, is_bot=False, first_name="Test"),
        text="test",
    )


@pytest.mark.asyncio
async def test_global_error_handler_logs_exception_and_notifies_user(caplog) -> None:
    message = _message()
    update = Update(update_id=1, message=message)
    event = ErrorEvent(update=update, exception=RuntimeError("database exploded"))

    with patch.object(Message, "answer", new_callable=AsyncMock) as answer, caplog.at_level(
        logging.ERROR
    ):
        await handle_error(event)

    answer.assert_awaited_once_with(
        "❌ خطایی غیرمنتظره رخ داد. لطفاً دوباره تلاش کنید."
    )
    assert "Unhandled exception while processing update" in caplog.text
    assert "database exploded" in caplog.text


@pytest.mark.asyncio
async def test_global_error_handler_uses_callback_message_when_update_has_no_message() -> None:
    callback_message = _message()
    callback_query = CallbackQuery(
        id="callback-1",
        from_user=callback_message.from_user,
        chat_instance="instance-1",
        message=callback_message,
    )
    update = Update(update_id=1, callback_query=callback_query)
    event = ErrorEvent(update=update, exception=RuntimeError("boom"))

    with patch.object(Message, "answer", new_callable=AsyncMock) as answer:
        await handle_error(event)

    answer.assert_awaited_once_with(
        "❌ خطایی غیرمنتظره رخ داد. لطفاً دوباره تلاش کنید."
    )


@pytest.mark.asyncio
async def test_global_error_handler_does_not_fail_when_update_has_no_user_message() -> None:
    update = Update(update_id=1)
    event = ErrorEvent(update=update, exception=RuntimeError("boom"))

    await handle_error(event)
