from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from callbacks.admin import AdminReferralRewardCallback
from core.telegram import edit_message_if_changed
from filters.admin import AdminPermissionFilter
from keyboards.admin_referral_reward import (
    admin_referral_reward_history_keyboard,
    admin_referral_reward_keyboard,
    admin_referral_reward_manual_keyboard,
)
from keyboards.admin_settings import admin_settings_keyboard
from models.bot_settings import BotSettings
from core.display import user_display_name
from models.referral_reward import ReferralRewardHistoryItem
from services.bot_settings import BotSettingsService
from services.referral import ReferralService
from states.admin import AdminSettingsStates


_REWARD_HISTORY_LIMIT = 10


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


@router.callback_query(AdminReferralRewardCallback.filter(F.action == "open"))
async def referral_reward_open_handler(
    callback: CallbackQuery,
    state: FSMContext,
    bot_settings_service: BotSettingsService,
) -> None:
    # Also serves as "cancel" for manual entry, so any pending state is dropped.
    await state.clear()
    settings = await bot_settings_service.get_settings()
    await _show_reward_editor(callback, settings)
    await callback.answer()


@router.callback_query(AdminReferralRewardCallback.filter(F.action.in_({"coins", "invites"})))
async def referral_reward_step_handler(
    callback: CallbackQuery,
    callback_data: AdminReferralRewardCallback,
    bot_settings_service: BotSettingsService,
) -> None:
    current = await bot_settings_service.get_settings()
    coins = current.referral_reward_coins
    invites = current.referral_reward_per_invites
    if callback_data.action == "coins":
        coins += callback_data.delta
    else:
        invites += callback_data.delta

    try:
        settings = await bot_settings_service.set_referral_reward(
            coins=coins, per_invites=invites
        )
    except ValueError:
        await callback.answer("حداقل مقدار ۱ است.", show_alert=True)
        return
    await _show_reward_editor(callback, settings)
    await callback.answer("ذخیره شد ✅")


@router.callback_query(AdminReferralRewardCallback.filter(F.action == "preset"))
async def referral_reward_preset_handler(
    callback: CallbackQuery,
    callback_data: AdminReferralRewardCallback,
    bot_settings_service: BotSettingsService,
) -> None:
    settings = await bot_settings_service.set_referral_reward(
        coins=callback_data.delta, per_invites=callback_data.value
    )
    await _show_reward_editor(callback, settings)
    await callback.answer("ذخیره شد ✅")


@router.callback_query(AdminReferralRewardCallback.filter(F.action == "manual"))
async def referral_reward_manual_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminSettingsStates.waiting_for_referral_reward)
    await edit_message_if_changed(
        message=callback.message,
        text=(
            "✏️ ورود دستی پاداش\n\n"
            "دو عدد را با فاصله بفرستید: «سکه» و «تعداد دعوت»\n"
            "مثال: <code>5 3</code> یعنی هر ۳ دعوت ثبت‌نام‌شده → ۵ سکه"
        ),
        reply_markup=admin_referral_reward_manual_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminSettingsStates.waiting_for_referral_reward)
async def referral_reward_manual_input_handler(
    message: Message,
    state: FSMContext,
    bot_settings_service: BotSettingsService,
) -> None:
    parsed = _parse_reward_input(message.text)
    if parsed is None:
        await message.answer(
            "❌ فرمت درست نیست. دو عدد صحیح بزرگ‌تر از صفر با فاصله بفرستید، مثلاً: 5 3",
            reply_markup=admin_referral_reward_manual_keyboard(),
        )
        return
    coins, per_invites = parsed
    settings = await bot_settings_service.set_referral_reward(
        coins=coins, per_invites=per_invites
    )
    await state.clear()
    await message.answer(
        "✅ ذخیره شد.\n\n" + _reward_editor_text(settings),
        reply_markup=admin_referral_reward_keyboard(settings),
    )


@router.callback_query(AdminReferralRewardCallback.filter(F.action == "history"))
async def referral_reward_history_handler(
    callback: CallbackQuery,
    referral_service: ReferralService,
) -> None:
    entries = await referral_service.get_recent_rewards(limit=_REWARD_HISTORY_LIMIT)
    await edit_message_if_changed(
        message=callback.message,
        text=_reward_history_text(entries),
        reply_markup=admin_referral_reward_history_keyboard(),
    )
    await callback.answer()


@router.callback_query(AdminReferralRewardCallback.filter(F.action == "back"))
async def referral_reward_back_handler(
    callback: CallbackQuery,
    bot_settings_service: BotSettingsService,
) -> None:
    settings = await bot_settings_service.get_settings()
    await _update_settings_message(callback, settings, "")


def _parse_reward_input(text: str | None) -> tuple[int, int] | None:
    """Accept "5 3", "5,3" or "5/3" (Persian digits included) as (coins, invites)."""
    normalized = (text or "").translate(_PERSIAN_DIGITS).replace(",", " ").replace("/", " ")
    parts = normalized.split()
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        return None
    coins, invites = int(parts[0]), int(parts[1])
    if coins <= 0 or invites <= 0:
        return None
    return coins, invites


_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


async def _show_reward_editor(callback: CallbackQuery, settings: BotSettings) -> None:
    await edit_message_if_changed(
        message=callback.message,
        text=_reward_editor_text(settings),
        reply_markup=admin_referral_reward_keyboard(settings),
    )


def _reward_editor_text(settings: BotSettings) -> str:
    coins = settings.referral_reward_coins
    invites = settings.referral_reward_per_invites
    rule = (
        f"هر دعوت ثبت‌نام‌شده → {coins} سکه"
        if invites == 1
        else f"هر {invites} دعوت ثبت‌نام‌شده → {coins} سکه"
    )
    return (
        "🎁 پاداش دعوت\n\n"
        f"قانون فعلی: {rule}\n\n"
        "با ➖ / ➕ مقدار را تغییر دهید یا یکی از پیش‌تنظیم‌ها را بزنید؛"
        " هر تغییر بلافاصله ذخیره می‌شود.\n"
        "پاداش فقط برای دعوت‌هایی داده می‌شود که ثبت‌نام را کامل کرده‌اند."
    )


def _reward_history_text(items: list[ReferralRewardHistoryItem]) -> str:
    lines = ["📜 آخرین پاداش‌های پرداخت‌شده\n"]
    if not items:
        lines.append("هنوز پاداشی پرداخت نشده است.")
        return "\n".join(lines)
    for item in items:
        entry = item.entry
        when = entry.created_at.strftime("%Y-%m-%d %H:%M")
        referrer = user_display_name(
            name=item.referrer_name, telegram_id=entry.referrer_id
        )
        triggered_by = user_display_name(
            name=item.triggered_by_name, telegram_id=entry.triggered_by_user_id
        )
        lines.append(
            f"• {when} — {referrer}: {entry.coins} سکه"
            f" (بابت {entry.invites_consumed} دعوت؛ آخرین: {triggered_by})"
        )
    return "\n".join(lines)


async def _update_settings_message(callback: CallbackQuery, settings: BotSettings, answer_text: str) -> None:
    text = _settings_text(settings)
    keyboard = admin_settings_keyboard(settings)
    await edit_message_if_changed(
        message=callback.message, text=text, reply_markup=keyboard
    )
    await callback.answer(answer_text or None)


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
