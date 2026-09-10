from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message

from keyboards.menu import main_menu
from keyboards.start import start_keyboard
from models.user import RegistrationStatus, User
from services.notification import NotificationService
from services.referral import ReferralService


router = Router()


async def send_welcome(message: Message, user: User, first_name: str) -> None:
    """Send the welcome message that matches the user's registration state.

    Shared with the force-subscription flow: a blocked /start never reaches
    ``start_handler``, so the welcome is re-sent once membership is verified.
    """
    if user.registration_status == RegistrationStatus.REGISTERED:
        await message.answer(
            f"سلام {first_name} 👋\n"
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


@router.message(CommandStart())
async def start_handler(
    message: Message,
    user: User,
    command: CommandObject,
    referral_service: ReferralService,
    notification_service: NotificationService,
) -> None:
    first_name = (
        message.from_user.first_name
        if message.from_user is not None
        else user.telegram_name
    )

    if user.registration_status == RegistrationStatus.REGISTERED:
        await send_welcome(message, user, first_name)
        return

    referrer_id = await referral_service.process_start(
        telegram_id=user.telegram_id,
        referral_code=command.args,
    )
    if referrer_id is not None:
        total = await referral_service.get_referral_count(referrer_id)
        await notification_service.referral_joined(
            referrer_id, first_name, total
        )

    await send_welcome(message, user, first_name)
