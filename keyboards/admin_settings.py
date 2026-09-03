from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from models.bot_settings import BotSettings


def admin_settings_keyboard(settings: BotSettings) -> InlineKeyboardMarkup:
    bot_label = "🟢 ربات روشن" if settings.bot_enabled else "🔴 ربات خاموش"
    maintenance_label = "🟠 حالت تعمیرات فعال" if settings.maintenance_mode else "⚪ حالت تعمیرات غیرفعال"
    antispam_label = "🟢 ضد اسپم فعال" if settings.antispam_enabled else "🔴 ضد اسپم خاموش"
    force_label = "🟢 عضویت اجباری فعال" if settings.force_subscription_enabled else "⚪ عضویت اجباری خاموش"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=bot_label, callback_data="admin_settings_toggle_bot"),
                InlineKeyboardButton(text=maintenance_label, callback_data="admin_settings_toggle_maintenance"),
            ],
            [
                InlineKeyboardButton(text=antispam_label, callback_data="admin_settings_toggle_antispam"),
                InlineKeyboardButton(text=force_label, callback_data="admin_settings_toggle_force_subscription"),
            ],
            [
                InlineKeyboardButton(text="📢 مدیریت عضویت اجباری", callback_data="admin_force_subscription_manage"),
            ],
        ]
    )
