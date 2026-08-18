from aiogram import F, Router
from aiogram.types import Message

from exceptions.user import UserNotFoundError
from services.user import UserService


router = Router()


@router.message(F.text == "👤 پروفایل")
async def profile_handler(
    message: Message,
    user_service: UserService,
) -> None:
    if message.from_user is None:
        return

    try:
        user = await user_service.get_user(message.from_user.id)
    except UserNotFoundError:
        await message.answer(
            "برای استفاده از امکانات ربات ابتدا ثبت نام کنید."
        )
        return

    await message.answer(
        "👤 پروفایل شما\n\n"
        f"نام: {user.name}\n"
        f"سن: {user.age}\n"
        f"سکه: {user.coins}\n"
        f"اخطار: {user.warnings}\n"
        f"وضعیت: {user.status.value}"
    )
