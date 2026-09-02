from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from filters.admin import AdminFilter
from keyboards.admin_settings import admin_settings_keyboard
from models.bot_settings import BotSettings
from services.bot_settings import BotSettingsService


router = Router()
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())


@router.message(F.text == "⚙️ تنظیمات ربات")
async def bot_settings_handler(
    message: Message,
    bot_settings_service: BotSettingsService,
) -> None:
    settings = await bot_settings_service.get_settings()
    await message.answer(
        _settings_text(settings),
        reply_markup=admin_settings_keyboard(settings),
    )


@router.callback_query(F.data == "admin_settings_toggle_bot")
async def toggle_bot_handler(
    callback: CallbackQuery,
    bot_settings_service: BotSettingsService,
) -> None:
    settings = await bot_settings_service.toggle_bot()
    await callback.message.edit_text(
        _settings_text(settings),
        reply_markup=admin_settings_keyboard(settings),
    )
    await callback.answer("وضعیت ربات تغییر کرد.")


@router.callback_query(F.data == "admin_settings_toggle_maintenance")
async def toggle_maintenance_handler(
    callback: CallbackQuery,
    bot_settings_service: BotSettingsService,
) -> None:
    settings = await bot_settings_service.toggle_maintenance()
    await callback.message.edit_text(
        _settings_text(settings),
        reply_markup=admin_settings_keyboard(settings),
    )
    await callback.answer("حالت تعمیرات تغییر کرد.")


@router.callback_query(F.data == "admin_settings_refresh")
async def refresh_settings_handler(
    callback: CallbackQuery,
    bot_settings_service: BotSettingsService,
) -> None:
    settings = await bot_settings_service.get_settings()
    await callback.message.edit_text(
        _settings_text(settings),
        reply_markup=admin_settings_keyboard(settings),
    )
    await callback.answer("بروزرسانی شد.")


def _settings_text(settings: BotSettings) -> str:
    bot_status = "🟢 روشن" if settings.bot_enabled else "🔴 خاموش"
    maintenance_status = "🟠 فعال" if settings.maintenance_mode else "⚪ غیرفعال"

    effective_status = "🟢 در دسترس کاربران"
    if not settings.bot_enabled:
        effective_status = "🔴 غیرفعال برای کاربران"
    elif settings.maintenance_mode:
        effective_status = "🟠 در حالت تعمیرات"

    return (
        "⚙️ تنظیمات ربات\n\n"
        f"وضعیت اصلی: {bot_status}\n"
        f"حالت تعمیرات: {maintenance_status}\n"
        f"وضعیت مؤثر: {effective_status}\n\n"
        "مدیران حتی در حالت خاموش یا تعمیرات به ربات دسترسی دارند."
    )
