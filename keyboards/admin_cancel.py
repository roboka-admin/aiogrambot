from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


admin_cancel_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="❌ لغو",
                callback_data="admin_cancel",
            )
        ]
    ]
)
