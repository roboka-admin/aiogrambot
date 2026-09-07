from unittest.mock import AsyncMock, MagicMock

import pytest

from callbacks.admin import AdminCreateConfirmCallback
from exceptions.user import UserNotFoundError
from handlers.admin_management import admin_create_confirm_handler, admin_create_id_handler
from models.admin import Admin
from states.admin import AdminManagementStates


@pytest.mark.asyncio
async def test_admin_create_id_handler_rejects_user_who_has_not_started_bot():
    message = MagicMock()
    message.text = "200"
    message.from_user.id = 100
    message.answer = AsyncMock()
    state = MagicMock()
    state.update_data = AsyncMock()
    admin_service = MagicMock()
    admin_service.get_admin = AsyncMock(return_value=None)
    admin_service.user_exists = AsyncMock(return_value=False)

    await admin_create_id_handler(message, state, admin_service)

    message.answer.assert_awaited_once_with(
        "❌ این کاربر هنوز ربات را شروع نکرده است. ابتدا ربات را برای او ارسال کنید تا /start کند."
    )
    state.update_data.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_create_confirm_handler_notifies_new_admin_after_success():
    callback = MagicMock()
    callback.from_user.id = 100
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    state = MagicMock()
    state.get_data = AsyncMock(return_value={"admin_id": 200, "permission_keys": ["support"]})
    state.get_state = AsyncMock(
        return_value=AdminManagementStates.waiting_for_permission_selection
    )
    state.clear = AsyncMock()
    admin_service = MagicMock()
    admin_service.create_managed_admin = AsyncMock(
        return_value=Admin(telegram_id=200)
    )
    notification_service = MagicMock()
    notification_service.admin_added = AsyncMock()

    await admin_create_confirm_handler(
        callback,
        state,
        admin_service,
        notification_service,
    )

    admin_service.create_managed_admin.assert_awaited_once_with(
        actor_telegram_id=100,
        telegram_id=200,
        permission_keys={"support"},
    )
    notification_service.admin_added.assert_awaited_once_with(200)
    state.clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_create_confirm_handler_does_not_notify_when_creation_fails():
    callback = MagicMock()
    callback.from_user.id = 100
    callback.answer = AsyncMock()
    state = MagicMock()
    state.get_data = AsyncMock(return_value={"admin_id": 200, "permission_keys": []})
    state.get_state = AsyncMock(
        return_value=AdminManagementStates.waiting_for_permission_selection
    )
    admin_service = MagicMock()
    admin_service.create_managed_admin = AsyncMock(side_effect=UserNotFoundError)
    notification_service = MagicMock()
    notification_service.admin_added = AsyncMock()

    await admin_create_confirm_handler(
        callback,
        state,
        admin_service,
        notification_service,
    )

    notification_service.admin_added.assert_not_awaited()
    callback.answer.assert_awaited_once_with(
        "❌ این کاربر هنوز ربات را شروع نکرده است. ابتدا ربات را برای او ارسال کنید تا /start کند.",
        show_alert=True,
    )
