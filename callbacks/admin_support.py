from aiogram.filters.callback_data import CallbackData


class AdminSupportListCallback(CallbackData, prefix="admin_support_list"):
    status: str


class AdminSupportTicketCallback(CallbackData, prefix="admin_support_ticket"):
    ticket_id: int


class AdminSupportBackCallback(CallbackData, prefix="admin_support_back"):
    pass
