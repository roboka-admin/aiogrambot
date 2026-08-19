from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from callbacks.admin import AdminUserActionCallback, AdminUsersCallback
from models.user import User


def user_actions_keyboard(user: User) -> InlineKeyboardMarkup:
    block_action = "unblock" if user.status.value == "blocked" else "block"
    block_text = "✅ رفع مسدودیت" if block_action == "unblock" else "🚫 مسدود کردن"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ افزایش سکه",
                    callback_data=AdminUserActionCallback(
                        action="add_coin",
                        telegram_id=user.telegram_id,
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="➖ کاهش سکه",
                    callback_data=AdminUserActionCallback(
                        action="remove_coin",
                        telegram_id=user.telegram_id,
                    ).pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚠️ افزودن اخطار",
                    callback_data=AdminUserActionCallback(
                        action="add_warning",
                        telegram_id=user.telegram_id,
                    ).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text=block_text,
                    callback_data=AdminUserActionCallback(
                        action=block_action,
                        telegram_id=user.telegram_id,
                    ).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت به کاربران",
                    callback_data=AdminUsersCallback(page=0).pack(),
                )
            ],
        ]
    )
