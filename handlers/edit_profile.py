from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from exceptions.user import UserNotFoundError
from keyboards.menu import edit_profile_menu, main_menu
from states.profile import EditProfileStates
from validators.register import validate_age, validate_name


router = Router()


async def _is_registered(message: Message, user: User | None) -> bool:
    return user is not None


@router.message(F.text == "✏️ ویرایش پروفایل")
async def edit_profile_handler(
    message: Message,
    user: User | None,
) -> None:
    if not await _is_registered(message, user):
        await message.answer("برای استفاده از امکانات ربات ابتدا ثبت نام کنید.")
        return

    await message.answer(
        "کدام مورد را می‌خواهید تغییر دهید؟",
        reply_markup=edit_profile_menu,
    )


@router.message(F.text == "✏️ تغییر نام")
async def change_name_handler(
    message: Message,
    state: FSMContext,
    user: User | None,
) -> None:
    if not await _is_registered(message, user):
        return

    await state.set_state(EditProfileStates.waiting_name)
    await message.answer("نام جدید خود را ارسال کنید:")


@router.message(F.text == "🎂 تغییر سن")
async def change_age_handler(
    message: Message,
    state: FSMContext,
    user: User | None,
) -> None:
    if not await _is_registered(message, user):
        return

    await state.set_state(EditProfileStates.waiting_age)
    await message.answer("سن جدید خود را ارسال کنید:")


@router.message(F.text == "❌ لغو")
async def cancel_edit_handler(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()
    await message.answer(
        "ویرایش لغو شد.",
        reply_markup=main_menu,
    )


@router.message(EditProfileStates.waiting_name, F.text)
async def save_name_handler(
    message: Message,
    state: FSMContext,
    user: User | None,
) -> None:
    if message.from_user is None or message.text is None or user is None:
        return

    name = message.text.strip()

    if not validate_name(name):
        await message.answer("❌ نام وارد شده معتبر نیست.")
        return

    try:
        await user_service.update_name(user.telegram_id, name)
    except UserNotFoundError:
        await state.clear()
        await message.answer("برای استفاده از امکانات ربات ابتدا ثبت نام کنید.")
        return

    await state.clear()
    await message.answer(
        "نام شما با موفقیت تغییر کرد ✅",
        reply_markup=main_menu,
    )


@router.message(EditProfileStates.waiting_name)
async def invalid_name_handler(message: Message) -> None:
    await message.answer("❌ لطفاً نام را فقط به صورت متن ارسال کنید.")


@router.message(EditProfileStates.waiting_age, F.text)
async def save_age_handler(
    message: Message,
    state: FSMContext,
    user: User | None,
) -> None:
    if message.from_user is None or message.text is None or user is None:
        return

    if not validate_age(message.text):
        await message.answer("❌ سن وارد شده معتبر نیست.")
        return

    try:
        await user_service.update_age(
            user.telegram_id,
            int(message.text),
        )
    except UserNotFoundError:
        await state.clear()
        await message.answer("برای استفاده از امکانات ربات ابتدا ثبت نام کنید.")
        return

    await state.clear()
    await message.answer(
        "سن شما با موفقیت تغییر کرد ✅",
        reply_markup=main_menu,
    )


@router.message(EditProfileStates.waiting_age)
async def invalid_age_handler(message: Message) -> None:
    await message.answer("❌ لطفاً سن را فقط به صورت عدد ارسال کنید.")
