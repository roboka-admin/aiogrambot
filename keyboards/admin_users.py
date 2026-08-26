from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from callbacks.admin import AdminBlockedUsersCallback, AdminUserCallback, AdminUsersCallback
from models.user import User


def _label(user: User) -> str:
    return user.name or user.telegram_name or "بدون نام"


def user_management_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔎 جستجوی کاربر", callback_data="admin_find_user"),
        InlineKeyboardButton(text="📋 فهرست کاربران", callback_data="admin_browse_users"),
    ], [InlineKeyboardButton(text="🚫 کاربران مسدود", callback_data="admin_blocked_users")]])


def users_keyboard(*, users: list[User], page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"👤 {_label(user)} | {user.telegram_id}", callback_data=AdminUserCallback(telegram_id=user.telegram_id, source="users", page=page).pack())] for user in users]
    navigation = []
    if page > 0: navigation.append(InlineKeyboardButton(text="⬅️ قبلی", callback_data=AdminUsersCallback(page=page - 1).pack()))
    navigation.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page + 1 < total_pages: navigation.append(InlineKeyboardButton(text="بعدی ➡️", callback_data=AdminUsersCallback(page=page + 1).pack()))
    rows += [navigation, [InlineKeyboardButton(text="🚫 کاربران مسدود", callback_data="admin_blocked_users"), InlineKeyboardButton(text="🔙 مدیریت کاربران", callback_data="admin_user_management")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def blocked_users_keyboard(*, users: list[User], page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"👤 {_label(user)} | {user.telegram_id}", callback_data=AdminUserCallback(telegram_id=user.telegram_id, source="blocked", page=page).pack())] for user in users]
    navigation = []
    if page > 0: navigation.append(InlineKeyboardButton(text="⬅️ قبلی", callback_data=AdminBlockedUsersCallback(page=page - 1).pack()))
    navigation.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page + 1 < total_pages: navigation.append(InlineKeyboardButton(text="بعدی ➡️", callback_data=AdminBlockedUsersCallback(page=page + 1).pack()))
    rows += [navigation, [InlineKeyboardButton(text="📋 همه کاربران", callback_data="admin_browse_users"), InlineKeyboardButton(text="🔙 مدیریت کاربران", callback_data="admin_user_management")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)
