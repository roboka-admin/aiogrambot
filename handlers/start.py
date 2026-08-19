from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from keyboards.menu import main_menu
from keyboards.start import start_keyboard
from models.user import User


router = Router()


@router.message(CommandStart())
async def start_handler(
    message: Message,
    user: User | None,
) -> None:
    if user is not None:
        await message.answer(
            f"سلام {message.from_user.first_name} 👋\n"
            "خوش آمدید.",
            reply_markup=main_menu,
        )
        return

    await message.answer(
        "سلام 👋\n"
        "به ربات خوش آمدید.\n"
        "برای شروع ثبت نام کنید:",
        reply_markup=start_keyboard,
    )
