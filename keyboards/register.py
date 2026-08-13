from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


cancel_register = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="لغو",
                callback_data="cancel_register"
            )
        ]
    ]
)