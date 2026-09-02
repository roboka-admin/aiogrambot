from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from models.bot_settings import BotSettings


def admin_settings_keyboard(settings: BotSettings) -> InlineKeyboardMarkup:
    bot_label = "🟢 ربات روشن" if settings.bot_enabled else "🔴 ربات خاموش"
    maintenance_label = (
        "🟠 حالت تعمیرات فعال"
        if settings.maintenance_mode
        else "⚪ حالت تعمیرات غیرفعال"
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=bot_label,
                    callback_data="admin_settings_toggle_bot",
                ),
                InlineKeyboardButton(
                    text=maintenance_label,
                    callback_data="admin_settings_toggle_maintenance",
                ),
            ],
        ]
    )
