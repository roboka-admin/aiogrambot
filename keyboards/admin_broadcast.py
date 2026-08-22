from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from callbacks.admin import (
    AdminBroadcastCancelCallback,
    AdminBroadcastConfirmCallback,
    AdminBroadcastEditCallback,
    AdminBroadcastStartCallback,
)


def broadcast_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ لغو")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def broadcast_preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 شروع ارسال",
                    callback_data=AdminBroadcastStartCallback().pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✏️ تغییر پیام",
                    callback_data=AdminBroadcastEditCallback().pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ لغو",
                    callback_data=AdminBroadcastCancelCallback().pack(),
                ),
            ],
        ]
    )
