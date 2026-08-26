from aiogram.filters.callback_data import CallbackData


class AdminUsersCallback(CallbackData, prefix="admin_users"):
    page: int


class AdminUserCallback(CallbackData, prefix="admin_user"):
    telegram_id: int
    source: str = "users"
    page: int = 0


class AdminUserActionCallback(CallbackData, prefix="admin_user_action"):
    action: str
    telegram_id: int
    source: str = "users"
    page: int = 0


class AdminUserAmountCallback(CallbackData, prefix="admin_user_amount"):
    action: str
    telegram_id: int


class AdminBroadcastStartCallback(CallbackData, prefix="admin_broadcast_start"):
    pass


class AdminBroadcastConfirmCallback(CallbackData, prefix="admin_broadcast_confirm"):
    pass


class AdminBroadcastEditCallback(CallbackData, prefix="admin_broadcast_edit"):
    pass


class AdminBroadcastCancelCallback(CallbackData, prefix="admin_broadcast_cancel"):
    pass


class AdminBlockedUsersCallback(CallbackData, prefix="admin_blocked_users"):
    page: int
