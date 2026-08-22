from enum import Enum

from aiogram.filters.callback_data import CallbackData


class CleanupAction(str, Enum):
    DELETE_CLOSED = "delete_closed"
    DELETE_ALL = "delete_all"


class AdminSupportListCallback(CallbackData, prefix="admin_support_list"):
    status: str
    page: int


class AdminSupportUserCallback(CallbackData, prefix="admin_support_user"):
    telegram_id: int
    status: str
    page: int


class AdminSupportTicketCallback(CallbackData, prefix="admin_support_ticket"):
    ticket_id: int
    telegram_id: int
    status: str
    page: int


class AdminSupportActionCallback(CallbackData, prefix="admin_support_action"):
    action: str
    telegram_id: int
    status: str
    page: int


class AdminSupportBackCallback(CallbackData, prefix="admin_support_back"):
    pass


class AdminSupportSettingsCallback(CallbackData, prefix="admin_support_settings"):
    pass


class AdminSupportSettingsBackCallback(CallbackData, prefix="admin_support_settings_back"):
    pass


class AdminSupportCleanupCallback(CallbackData, prefix="admin_support_cleanup"):
    action: CleanupAction


class AdminSupportCleanupConfirmCallback(CallbackData, prefix="admin_support_cleanup_confirm"):
    action: CleanupAction


class AdminSupportCleanupCancelCallback(CallbackData, prefix="admin_support_cleanup_cancel"):
    pass
