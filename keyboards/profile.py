from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from callbacks.profile import ProfileCallback


def profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ تغییر نام",
                    callback_data=ProfileCallback(action="edit_name").pack(),
                ),
                InlineKeyboardButton(
                    text="🎂 تغییر سن",
                    callback_data=ProfileCallback(action="edit_age").pack(),
                ),
            ],
        ]
    )


def profile_edit_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ انصراف",
                    callback_data=ProfileCallback(action="cancel_edit").pack(),
                )
            ],
        ]
    )
