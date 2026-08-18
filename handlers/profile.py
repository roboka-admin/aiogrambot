from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from exceptions.user import UserNotFoundError
from services.user import UserService


router = Router()


@router.message(Command("profile"))
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
            "شما هنوز ثبت نام نکرده‌اید."
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
