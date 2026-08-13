from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from keyboards.start import start_keyboard


router = Router()


@router.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "سلام 👋\n"
        "به ربات خوش آمدید.\n"
        "برای شروع ثبت نام کنید:",
        reply_markup=start_keyboard
    )