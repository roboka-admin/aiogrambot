from aiogram.filters.callback_data import CallbackData


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


class AdminSupportCleanupCallback(CallbackData, prefix="admin_support_cleanup"):
    action: str


class AdminSupportCleanupConfirmCallback(CallbackData, prefix="admin_support_cleanup_confirm"):
    action: str


class AdminSupportCleanupCancelCallback(CallbackData, prefix="admin_support_cleanup_cancel"):
    pass
