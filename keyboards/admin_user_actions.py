from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from callbacks.admin import (
    AdminBlockedUsersCallback,
    AdminUserActionCallback,
    AdminUsersCallback,
)
from models.user import User


def user_actions_keyboard(
    user: User,
    *,
    source: str = "users",
    page: int = 0,
) -> InlineKeyboardMarkup:
    block_action = "unblock" if user.status.value == "blocked" else "block"
    block_text = "✅ رفع مسدودیت" if block_action == "unblock" else "🚫 مسدود کردن"

    action_callback = lambda action: AdminUserActionCallback(
        action=action,
        telegram_id=user.telegram_id,
        source=source,
        page=page,
    ).pack()

    back_callback = (
        AdminBlockedUsersCallback(page=page).pack()
        if source == "blocked"
        else AdminUsersCallback(page=page).pack()
    )
    back_text = "⬅️ بازگشت به کاربران مسدود" if source == "blocked" else "⬅️ بازگشت به کاربران"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ افزایش سکه", callback_data=action_callback("add_coin")),
                InlineKeyboardButton(text="➖ کاهش سکه", callback_data=action_callback("remove_coin")),
            ],
            [
                InlineKeyboardButton(text="⚠️ افزودن اخطار", callback_data=action_callback("add_warning")),
                InlineKeyboardButton(text=block_text, callback_data=action_callback(block_action)),
            ],
            [InlineKeyboardButton(text=back_text, callback_data=back_callback)],
        ]
    )