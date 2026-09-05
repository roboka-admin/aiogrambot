from collections.abc import Collection

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from core.admin_permissions import ADMIN_PERMISSION_REGISTRY


def build_admin_menu(permission_keys: Collection[str]) -> ReplyKeyboardMarkup:
    """Build the admin panel menu from the central permission registry."""
    allowed = set(permission_keys)
    buttons = [
        KeyboardButton(text=permission.title)
        for permission in ADMIN_PERMISSION_REGISTRY
        if permission.key in allowed
    ]

    rows = [buttons[index : index + 2] for index in range(0, len(buttons), 2)]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


# Kept for existing callers/tests that need the complete owner menu.
admin_menu = build_admin_menu(
    permission.key for permission in ADMIN_PERMISSION_REGISTRY
)
