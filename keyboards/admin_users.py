from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from callbacks.admin import AdminBlockedUsersCallback, AdminUserCallback, AdminUsersCallback
from models.user import User


def users_keyboard(
    *,
    users: list[User],
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="🔎 جستجوی کاربر با ID", callback_data="admin_find_user")]
    ]

    for user in users:
        rows.append([
            InlineKeyboardButton(
                text=f"👤 {user.name} | {user.telegram_id}",
                callback_data=AdminUserCallback(
                    telegram_id=user.telegram_id
                ).pack(),
            )
        ])

    navigation: list[InlineKeyboardButton] = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text="◀️ قبلی",
                callback_data=AdminUsersCallback(page=page - 1).pack(),
            )
        )

    navigation.append(
        InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop")
    )

    if page + 1 < total_pages:
        navigation.append(
            InlineKeyboardButton(
                text="بعدی ▶️",
                callback_data=AdminUsersCallback(page=page + 1).pack(),
            )
        )

    rows.append(navigation)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def blocked_users_keyboard(
    *,
    users: list[User],
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="🔎 جستجوی کاربر با ID", callback_data="admin_find_user")],
        [InlineKeyboardButton(text="🔙 بازگشت به لیست کاربران", callback_data=AdminUsersCallback(page=0).pack())],
    ]

    for user in users:
        rows.append([
            InlineKeyboardButton(
                text=f"👤 {user.name} | {user.telegram_id}",
                callback_data=AdminUserCallback(
                    telegram_id=user.telegram_id
                ).pack(),
            )
        ])

    navigation: list[InlineKeyboardButton] = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text="◀️ قبلی",
                callback_data=AdminBlockedUsersCallback(page=page - 1).pack(),
            )
        )

    navigation.append(
        InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop")
    )

    if page + 1 < total_pages:
        navigation.append(
            InlineKeyboardButton(
                text="بعدی ▶️",
                callback_data=AdminBlockedUsersCallback(page=page + 1).pack(),
            )
        )

    rows.append(navigation)
    return InlineKeyboardMarkup(inline_keyboard=rows)
