from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from filters.admin import AdminFilter
from keyboards.admin import admin_menu


router = Router()
router.message.filter(AdminFilter())


@router.message(Command("admin"))
async def admin_handler(message: Message) -> None:
    await message.answer(
        "👨‍💼 پنل مدیریت\n\n"
        "یکی از گزینه‌ها را انتخاب کنید:",
        reply_markup=admin_menu,
    )
