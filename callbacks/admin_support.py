from aiogram.filters.callback_data import CallbackData


class AdminSupportListCallback(CallbackData, prefix="admin_support_list"):
    status: str
    page: int


class AdminSupportUserCallback(CallbackData, prefix="admin_support_user"):
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
