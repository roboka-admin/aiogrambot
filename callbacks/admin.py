from aiogram.filters.callback_data import CallbackData


class AdminUsersCallback(CallbackData, prefix="admin_users"):
    page: int


class AdminUserCallback(CallbackData, prefix="admin_user"):
    telegram_id: int


class AdminUserActionCallback(CallbackData, prefix="admin_user_action"):
    action: str
    telegram_id: int
