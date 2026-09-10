from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from core.telegram import edit_message_if_changed
from filters.admin import AdminPermissionFilter
from keyboards.admin_cancel import admin_cancel_keyboard
from keyboards.admin_settings import admin_settings_keyboard
from models.bot_settings import BotSettings
from services.bot_settings import BotSettingsService
from states.admin import AdminSettingsStates


router = Router()
router.message.filter(AdminPermissionFilter("settings"))
router.callback_query.filter(AdminPermissionFilter("settings"))


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


@router.callback_query(F.data == "admin_settings_referral_reward")
async def referral_reward_start_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminSettingsStates.waiting_for_referral_reward_coins)
    # ``source`` tells the shared admin_cancel handler which screen to restore.
    await state.update_data(source="settings")
    await callback.answer()
    if callback.message is not None:
        await callback.message.answer(
            "🎁 تنظیم پاداش دعوت\n\n"
            "مرحله ۱ از ۲: تعداد سکه‌ای که به ازای هر مرحله پاداش داده می‌شود را به صورت عدد ارسال کنید:",
            reply_markup=admin_cancel_keyboard,
        )


@router.message(AdminSettingsStates.waiting_for_referral_reward_coins)
async def referral_reward_coins_handler(message: Message, state: FSMContext) -> None:
    coins = _parse_positive_int(message.text)
    if coins is None:
        await message.answer(
            "❌ تعداد سکه باید یک عدد صحیح بزرگ‌تر از صفر باشد. دوباره ارسال کنید:",
            reply_markup=admin_cancel_keyboard,
        )
        return
    await state.update_data(referral_reward_coins=coins)
    await state.set_state(AdminSettingsStates.waiting_for_referral_reward_per_invites)
    await message.answer(
        f"مرحله ۲ از ۲: به ازای هر چند دعوتِ ثبت‌نام‌شده، {coins} سکه داده شود؟ (عدد ارسال کنید)",
        reply_markup=admin_cancel_keyboard,
    )


@router.message(AdminSettingsStates.waiting_for_referral_reward_per_invites)
async def referral_reward_per_invites_handler(
    message: Message,
    state: FSMContext,
    bot_settings_service: BotSettingsService,
) -> None:
    per_invites = _parse_positive_int(message.text)
    if per_invites is None:
        await message.answer(
            "❌ تعداد دعوت باید یک عدد صحیح بزرگ‌تر از صفر باشد. دوباره ارسال کنید:",
            reply_markup=admin_cancel_keyboard,
        )
        return
    data = await state.get_data()
    settings = await bot_settings_service.set_referral_reward(
        coins=data["referral_reward_coins"],
        per_invites=per_invites,
    )
    await state.clear()
    await message.answer(
        f"✅ پاداش دعوت تنظیم شد: {settings.referral_reward_coins} سکه"
        f" به ازای هر {settings.referral_reward_per_invites} دعوت ثبت‌نام‌شده.\n\n"
        f"{_settings_text(settings)}",
        reply_markup=admin_settings_keyboard(settings),
    )


def _parse_positive_int(text: str | None) -> int | None:
    value = (text or "").strip()
    if not value.isdigit() or int(value) <= 0:
        return None
    return int(value)


async def _update_settings_message(callback: CallbackQuery, settings: BotSettings, answer_text: str) -> None:
    text = _settings_text(settings)
    keyboard = admin_settings_keyboard(settings)
    await edit_message_if_changed(
        message=callback.message, text=text, reply_markup=keyboard
    )
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
        f"وضعیت مؤثر: {effective_status}\n"
        f"پاداش دعوت: {settings.referral_reward_coins} سکه"
        f" به ازای هر {settings.referral_reward_per_invites} دعوت ثبت‌نام‌شده\n\n"
        "مدیران حتی در حالت خاموش یا تعمیرات به ربات دسترسی دارند."
    )
