from aiogram.filters.callback_data import CallbackData


class ProfileCallback(CallbackData, prefix="profile"):
    """action: "edit_name" | "edit_age" | "cancel_edit" """

    action: str
