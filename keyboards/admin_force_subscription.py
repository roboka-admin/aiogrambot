from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from models.force_subscription import ForceSubscriptionTarget


def admin_force_subscription_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ افزودن کانال/گروه", callback_data="admin_force_subscription_add")],
            [InlineKeyboardButton(text="📋 فهرست مقصدها", callback_data="admin_force_subscription_list")],
        ]
    )


def admin_force_subscription_add_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ لغو", callback_data="admin_force_subscription_cancel_add")],
        ]
    )


def admin_force_subscription_list_keyboard(
    targets: list[ForceSubscriptionTarget],
) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="➕ افزودن کانال/گروه", callback_data="admin_force_subscription_add")]
    ]
    for target in targets:
        state = "🟢" if target.is_active else "⚪"
        rows.append([
            InlineKeyboardButton(
                text=f"{state} {target.title}",
                callback_data=f"admin_force_subscription_toggle:{target.chat_id}",
            ),
            InlineKeyboardButton(
                text="🗑 حذف",
                callback_data=f"admin_force_subscription_delete:{target.chat_id}",
            ),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)
