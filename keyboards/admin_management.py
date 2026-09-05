from collections.abc import Collection, Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from callbacks.admin import (
    AdminCreateCancelCallback,
    AdminCreateConfirmCallback,
    AdminCreatePermissionCallback,
    AdminManagementCallback,
)
from models.admin import Admin, AdminPermission


def admin_management_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ افزودن ادمین",
                    callback_data=AdminManagementCallback(action="create").pack(),
                ),
                InlineKeyboardButton(
                    text="👥 فهرست ادمین‌ها",
                    callback_data=AdminManagementCallback(action="list").pack(),
                ),
            ]
        ]
    )


def admins_keyboard(admins: Sequence[Admin]) -> InlineKeyboardMarkup:
    rows = []
    for admin in admins:
        if admin.role.value == "owner":
            label = f"👑 {admin.telegram_id}"
        else:
            status = "🟢" if admin.status.value == "active" else "🔴"
            label = f"{status} {admin.telegram_id}"
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=AdminManagementCallback(
                        action="view", telegram_id=admin.telegram_id
                    ).pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="➕ افزودن ادمین",
                callback_data=AdminManagementCallback(action="create").pack(),
            ),
            InlineKeyboardButton(
                text="🔙 بازگشت",
                callback_data=AdminManagementCallback(action="back").pack(),
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_detail_keyboard(admin: Admin, *, can_manage: bool = True) -> InlineKeyboardMarkup:
    if admin.role.value == "owner" or not can_manage:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 فهرست ادمین‌ها",
                        callback_data=AdminManagementCallback(action="list").pack(),
                    )
                ]
            ]
        )

    status_action = "deactivate" if admin.status.value == "active" else "activate"
    status_text = "⛔ غیرفعال کردن" if status_action == "deactivate" else "✅ فعال کردن"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔐 مدیریت دسترسی‌ها",
                    callback_data=AdminManagementCallback(
                        action="permissions", telegram_id=admin.telegram_id
                    ).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text=status_text,
                    callback_data=AdminManagementCallback(
                        action=status_action, telegram_id=admin.telegram_id
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="🗑 حذف",
                    callback_data=AdminManagementCallback(
                        action="delete", telegram_id=admin.telegram_id
                    ).pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 فهرست ادمین‌ها",
                    callback_data=AdminManagementCallback(action="list").pack(),
                )
            ],
        ]
    )


def permission_selection_keyboard(
    permissions: Sequence[AdminPermission], selected: Collection[str]
) -> InlineKeyboardMarkup:
    selected = set(selected)
    rows = []
    for permission in permissions:
        mark = "✅" if permission.key in selected else "⬜"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark} {permission.title}",
                    callback_data=AdminCreatePermissionCallback(
                        permission_key=permission.key
                    ).pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="✅ ثبت ادمین",
                callback_data=AdminCreateConfirmCallback().pack(),
            ),
            InlineKeyboardButton(
                text="❌ لغو",
                callback_data=AdminCreateCancelCallback().pack(),
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
