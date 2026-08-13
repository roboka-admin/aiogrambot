from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from exceptions.user import UserAlreadyExistsError
from keyboards.register import cancel_register
from keyboards.start import start_keyboard
from services.register import RegisterService
from states.register import RegisterStates
from validators.register import validate_age, validate_name


router = Router()


@router.callback_query(F.data == "register")
async def start_registration(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """
    Start the registration process.
    """

    await callback.answer()

    await state.set_state(RegisterStates.waiting_name)

    if callback.message:
        await callback.message.edit_text(
            text="لطفاً نام خود را وارد کنید.",
            reply_markup=cancel_register,
        )


@router.message(RegisterStates.waiting_name, F.text)
async def process_name(
    message: Message,
    state: FSMContext,
) -> None:
    """
    Handle user's name.
    """

    name = message.text.strip()

    if not validate_name(name):
        await message.answer(
            "❌ نام وارد شده معتبر نیست."
        )
        return

    await state.update_data(name=name)

    await state.set_state(RegisterStates.waiting_age)

    await message.answer(
        "لطفاً سن خود را وارد کنید."
    )


@router.message(RegisterStates.waiting_name)
async def invalid_name(
    message: Message,
) -> None:
    await message.answer(
        "❌ لطفاً نام را فقط به صورت متن ارسال کنید."
    )


@router.message(RegisterStates.waiting_age, F.text)
async def process_age(
    message: Message,
    state: FSMContext,
    register_service: RegisterService,
) -> None:
    """
    Handle user's age and complete registration.
    """

    if not validate_age(message.text):
        await message.answer(
            "❌ سن وارد شده معتبر نیست."
        )
        return

    data = await state.get_data()

    try:

        user = await register_service.register(
            telegram_id=message.from_user.id,
            name=data["name"],
            age=int(message.text),
        )

    except UserAlreadyExistsError:

        await message.answer(
            "❌ شما قبلاً ثبت نام کرده‌اید."
        )

        await state.clear()

        return

    await state.clear()

    await message.answer(
        f"✅ ثبت نام با موفقیت انجام شد.\n\n"
        f"👤 نام: {user.name}\n"
        f"🎂 سن: {user.age}"
    )


@router.message(RegisterStates.waiting_age)
async def invalid_age(
    message: Message,
) -> None:
    await message.answer(
        "❌ لطفاً سن را فقط به صورت عدد ارسال کنید."
    )


@router.callback_query(F.data == "cancel_register")
async def cancel_registration(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """
    Cancel registration.
    """

    await callback.answer()

    await state.clear()

    if callback.message:
        await callback.message.edit_text(
            text="ثبت نام لغو شد.",
            reply_markup=start_keyboard,
        )