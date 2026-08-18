from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from exceptions.user import UserNotFoundError
from keyboards.menu import edit_profile_menu, main_menu
from services.user import UserService
from states.profile import EditProfileStates


router = Router()


async def _is_registered(message: Message, user_service: UserService) -> bool:
    if message.from_user is None:
        return False
    return await user_service.exists(message.from_user.id)


@router.message(F.text == "✏️ ویرایش پروفایل")
async def edit_profile_handler(
    message: Message,
    user_service: UserService,
) -> None:
    if not await _is_registered(message, user_service):
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
    user_service: UserService,
) -> None:
    if not await _is_registered(message, user_service):
        return

    await state.set_state(EditProfileStates.waiting_name)
    await message.answer("نام جدید خود را ارسال کنید:")


@router.message(EditProfileStates.waiting_name)
async def save_name_handler(
    message: Message,
    state: FSMContext,
    user_service: UserService,
) -> None:
    if message.from_user is None or message.text is None:
        await message.answer("لطفاً نام را به صورت متن ارسال کنید.")
        return

    try:
        await user_service.update_name(message.from_user.id, message.text)
    except ValueError:
        await message.answer("نام معتبر نیست. دوباره ارسال کنید.")
        return
    except UserNotFoundError:
        await state.clear()
        await message.answer(
            "برای استفاده از امکانات ربات ابتدا ثبت نام کنید.",
            reply_markup=None,
        )
        return

    await state.clear()
    await message.answer(
        "نام شما با موفقیت تغییر کرد ✅",
        reply_markup=main_menu,
    )


@router.message(F.text == "🎂 تغییر سن")
async def change_age_handler(
    message: Message,
    state: FSMContext,
    user_service: UserService,
) -> None:
    if not await _is_registered(message, user_service):
        return

    await state.set_state(EditProfileStates.waiting_age)
    await message.answer("سن جدید خود را ارسال کنید:")


@router.message(EditProfileStates.waiting_age)
async def save_age_handler(
    message: Message,
    state: FSMContext,
    user_service: UserService,
) -> None:
    if message.from_user is None or message.text is None:
        await message.answer("لطفاً سن را به صورت عدد ارسال کنید.")
        return

    try:
        age = int(message.text)
        await user_service.update_age(message.from_user.id, age)
    except ValueError:
        await message.answer("سن باید یک عدد بین 1 تا 120 باشد.")
        return
    except UserNotFoundError:
        await state.clear()
        await message.answer("برای استفاده از امکانات ربات ابتدا ثبت نام کنید.")
        return

    await state.clear()
    await message.answer(
        "سن شما با موفقیت تغییر کرد ✅",
        reply_markup=main_menu,
    )


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
