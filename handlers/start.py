from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message

from keyboards.menu import main_menu
from keyboards.start import start_keyboard
from models.user import RegistrationStatus, User
from services.referral import ReferralService


router = Router()


@router.message(CommandStart())
async def start_handler(
    message: Message,
    user: User,
    command: CommandObject,
    referral_service: ReferralService,
) -> None:
    if user.registration_status == RegistrationStatus.REGISTERED:
        await message.answer(
            f"سلام {message.from_user.first_name} 👋\n"
            "خوش آمدید.",
            reply_markup=main_menu,
        )
        return

    await referral_service.process_start(
        telegram_id=user.telegram_id,
        referral_code=command.args,
    )

    await message.answer(
        "سلام 👋\n"
        "به ربات خوش آمدید.\n"
        "برای شروع ثبت نام کنید:",
        reply_markup=start_keyboard,
    )
