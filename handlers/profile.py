from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from callbacks.profile import ProfileCallback
from core.display import normalize_digits, user_status_label
from core.jalali import format_jalali_date
from core.telegram import edit_message_if_changed
from exceptions.user import UserNotFoundError
from keyboards.profile import profile_edit_keyboard, profile_keyboard
from middlewares.registration import RegistrationRequiredMiddleware
from models.user import User
from services.referral import ReferralRewardProgress, ReferralService
from services.user import MAX_WARNINGS, UserService
from states.profile import EditProfileStates
from validators.register import validate_age, validate_name


router = Router()
router.message.middleware(RegistrationRequiredMiddleware())
router.callback_query.middleware(RegistrationRequiredMiddleware())


@router.message(F.text == "👤 پروفایل")
async def profile_handler(
    message: Message,
    user: User,
    referral_service: ReferralService,
) -> None:
    progress = await referral_service.get_reward_progress(user.telegram_id)
    await message.answer(
        _profile_text(user, progress),
        reply_markup=profile_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(ProfileCallback.filter(F.action == "edit_name"))
async def edit_name_start_handler(
    callback: CallbackQuery, state: FSMContext, user: User
) -> None:
    await state.set_state(EditProfileStates.waiting_name)
    await edit_message_if_changed(
        message=callback.message,
        text=(
            "✏️ تغییر نام\n\n"
            f"نام فعلی: <b>{escape(user.name or '')}</b>\n\n"
            "نام جدید را ارسال کنید:"
        ),
        reply_markup=profile_edit_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(ProfileCallback.filter(F.action == "edit_age"))
async def edit_age_start_handler(
    callback: CallbackQuery, state: FSMContext, user: User
) -> None:
    await state.set_state(EditProfileStates.waiting_age)
    await edit_message_if_changed(
        message=callback.message,
        text=(
            "🎂 تغییر سن\n\n"
            f"سن فعلی: <b>{user.age}</b>\n\n"
            "سن جدید را به صورت عدد ارسال کنید:"
        ),
        reply_markup=profile_edit_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(ProfileCallback.filter(F.action == "cancel_edit"))
async def cancel_edit_handler(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    referral_service: ReferralService,
) -> None:
    await state.clear()
    progress = await referral_service.get_reward_progress(user.telegram_id)
    await edit_message_if_changed(
        message=callback.message,
        text=_profile_text(user, progress),
        reply_markup=profile_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer("انصراف داده شد.")


@router.message(EditProfileStates.waiting_name, F.text)
async def save_name_handler(
    message: Message,
    state: FSMContext,
    user: User,
    user_service: UserService,
    referral_service: ReferralService,
) -> None:
    name = (message.text or "").strip()
    if not validate_name(name):
        await message.answer(
            "❌ نام باید حداقل ۲ حرف باشد و فقط عدد نباشد. دوباره ارسال کنید:",
            reply_markup=profile_edit_keyboard(),
        )
        return
    try:
        updated = await user_service.update_name(user.telegram_id, name)
    except UserNotFoundError:
        await state.clear()
        return
    await state.clear()
    await _send_updated_profile(message, updated, referral_service, "✅ نام شما تغییر کرد.")


@router.message(EditProfileStates.waiting_name)
async def invalid_name_handler(message: Message) -> None:
    await message.answer(
        "❌ لطفاً نام را فقط به صورت متن ارسال کنید.",
        reply_markup=profile_edit_keyboard(),
    )


@router.message(EditProfileStates.waiting_age, F.text)
async def save_age_handler(
    message: Message,
    state: FSMContext,
    user: User,
    user_service: UserService,
    referral_service: ReferralService,
) -> None:
    raw_age = normalize_digits((message.text or "").strip())
    if not validate_age(raw_age):
        await message.answer(
            "❌ سن باید عددی بین ۱ تا ۱۲۰ باشد. دوباره ارسال کنید:",
            reply_markup=profile_edit_keyboard(),
        )
        return
    try:
        updated = await user_service.update_age(user.telegram_id, int(raw_age))
    except UserNotFoundError:
        await state.clear()
        return
    await state.clear()
    await _send_updated_profile(message, updated, referral_service, "✅ سن شما تغییر کرد.")


@router.message(EditProfileStates.waiting_age)
async def invalid_age_handler(message: Message) -> None:
    await message.answer(
        "❌ لطفاً سن را فقط به صورت عدد ارسال کنید.",
        reply_markup=profile_edit_keyboard(),
    )


async def _send_updated_profile(
    message: Message, user: User, referral_service: ReferralService, notice: str
) -> None:
    """Show the refreshed profile right after an edit so the change is visible."""
    progress = await referral_service.get_reward_progress(user.telegram_id)
    await message.answer(
        f"{notice}\n\n{_profile_text(user, progress)}",
        reply_markup=profile_keyboard(),
        parse_mode="HTML",
    )


def _profile_text(user: User, progress: ReferralRewardProgress) -> str:
    """Build the profile card. Every user-provided value is HTML-escaped."""
    identity_lines = [
        f"├ نام: <b>{escape(user.name or '—')}</b>",
        f"├ سن: <b>{user.age if user.age is not None else '—'}</b>",
    ]
    if user.username:
        identity_lines.append(f"├ نام کاربری: @{escape(user.username)}")
    identity_lines.append(f"└ شناسه: <code>{user.telegram_id}</code>")

    return (
        "👤 <b>پروفایل شما</b>\n\n"
        "📇 <b>مشخصات</b>\n"
        + "\n".join(identity_lines)
        + "\n\n"
        "💰 <b>دارایی</b>\n"
        f"├ موجودی: <b>{user.coins}</b> سکه\n"
        f"└ کسب‌شده از دعوت: <b>{progress.total_coins_earned}</b> سکه\n\n"
        "🛡 <b>وضعیت حساب</b>\n"
        f"├ وضعیت: {user_status_label(user.status)}\n"
        f"└ اخطار: <b>{user.warnings}</b> از {MAX_WARNINGS}\n\n"
        f"📅 عضو از: {format_jalali_date(user.first_seen_at)}\n\n"
        "💡 برای دعوت دوستان و کسب سکه از دکمهٔ «👥 دعوت دوستان» در منو استفاده کنید."
    )
