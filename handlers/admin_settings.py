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
async def bot_settings_handler(message: Message, bot_settings_service: BotSettingsService) -> None:
    settings = await bot_settings_service.get_settings()
    await message.answer(_settings_text(settings), reply_markup=admin_settings_keyboard(settings))


@router.callback_query(F.data == "admin_settings_toggle_bot")
async def toggle_bot_handler(callback: CallbackQuery, bot_settings_service: BotSettingsService) -> None:
    settings = await bot_settings_service.toggle_bot()
    await _update_settings_message(callback, settings, "وضعیت ربات تغییر کرد.")


@router.callback_query(F.data == "admin_settings_toggle_maintenance")
async def toggle_maintenance_handler(callback: CallbackQuery, bot_settings_service: BotSettingsService) -> None:
    settings = await bot_settings_service.toggle_maintenance()
    await _update_settings_message(callback, settings, "حالت تعمیرات تغییر کرد.")


@router.callback_query(F.data == "admin_settings_toggle_antispam")
async def toggle_antispam_handler(callback: CallbackQuery, bot_settings_service: BotSettingsService) -> None:
    settings = await bot_settings_service.toggle_antispam()
    await _update_settings_message(callback, settings, "وضعیت ضد اسپم تغییر کرد.")


@router.callback_query(F.data == "admin_settings_toggle_force_subscription")
async def toggle_force_subscription_handler(callback: CallbackQuery, bot_settings_service: BotSettingsService) -> None:
    settings = await bot_settings_service.toggle_force_subscription()
    await _update_settings_message(callback, settings, "وضعیت عضویت اجباری تغییر کرد.")


async def _update_settings_message(callback: CallbackQuery, settings: BotSettings, answer_text: str) -> None:
    text = _settings_text(settings)
    keyboard = admin_settings_keyboard(settings)
    if callback.message is not None:
        if callback.message.text != text or callback.message.reply_markup != keyboard:
            await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer(answer_text)


def _settings_text(settings: BotSettings) -> str:
    bot_status = "🟢 روشن" if settings.bot_enabled else "🔴 خاموش"
    maintenance_status = "🟠 فعال" if settings.maintenance_mode else "⚪ غیرفعال"
    antispam_status = "🟢 فعال" if settings.antispam_enabled else "🔴 خاموش"
    force_status = "🟢 فعال" if settings.force_subscription_enabled else "⚪ خاموش"

    effective_status = "🟢 در دسترس کاربران"
    if not settings.bot_enabled:
        effective_status = "🔴 غیرفعال برای کاربران"
    elif settings.maintenance_mode:
        effective_status = "🟠 در حالت تعمیرات"

    return (
        "⚙️ تنظیمات ربات\n\n"
        f"وضعیت اصلی: {bot_status}\n"
        f"حالت تعمیرات: {maintenance_status}\n"
        f"ضد اسپم: {antispam_status}\n"
        f"عضویت اجباری: {force_status}\n"
        f"وضعیت مؤثر: {effective_status}\n\n"
        "مدیران حتی در حالت خاموش یا تعمیرات به ربات دسترسی دارند."
    )
