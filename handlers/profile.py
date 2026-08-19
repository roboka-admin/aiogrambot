from aiogram import F, Router
from aiogram.types import Message

from models.user import User


router = Router()


@router.message(F.text == "👤 پروفایل")
async def profile_handler(
    message: Message,
    user: User | None,
) -> None:
    if user is None:
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
