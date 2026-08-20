import json
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import ADMIN_IDS
from keyboards.menu import main_menu, support_menu
from models.user import User
from services.support import SupportService
from states.support import SupportStates
from validators.support import validate_support_message


router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text == "🆘 پشتیبانی")
async def start_support_handler(
    message: Message,
    state: FSMContext,
    user: User | None,
) -> None:
    if user is None:
        await message.answer(
            "برای استفاده از امکانات ربات ابتدا ثبت نام کنید."
        )
        return

    await state.set_state(SupportStates.waiting_message)
    await message.answer(
        "پیام خود را برای پشتیبانی ارسال کنید.\n"
        "می‌توانید متن، عکس، ویدیو، فایل، صوت، ویس، استیکر، گیف یا ویدیو مسیج ارسال کنید.",
        reply_markup=support_menu,
    )


@router.message(SupportStates.waiting_message, F.text == "❌ لغو")
async def cancel_support_handler(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()
    await message.answer(
        "ارسال پیام پشتیبانی لغو شد.",
        reply_markup=main_menu,
    )


@router.message(SupportStates.waiting_message)
async def submit_support_handler(
    message: Message,
    state: FSMContext,
    user: User | None,
    support_service: SupportService,
    bot: Bot,
) -> None:
    if user is None or message.from_user is None:
        await state.clear()
        await message.answer(
            "برای استفاده از امکانات ربات ابتدا ثبت نام کنید.",
            reply_markup=main_menu,
        )
        return

    if not validate_support_message(message):
        await message.answer(
            "❌ این نوع پیام پشتیبانی نمی‌شود یا متن آن بیش از حد طولانی است."
        )
        return

    payload = _serialize_support_message(message)
    ticket = await support_service.create_ticket(
        user_telegram_id=user.telegram_id,
        message=payload,
    )

    await _notify_admins(
        bot=bot,
        message=message,
        ticket_id=ticket.id,
        user=user,
    )

    await state.clear()
    await message.answer(
        f"✅ پیام شما با شماره پیگیری #{ticket.id} ثبت شد.",
        reply_markup=main_menu,
    )


def _serialize_support_message(message: Message) -> str:
    payload: dict[str, str | None] = {
        "content_type": message.content_type.value,
        "text": message.text,
        "caption": message.caption,
        "file_id": _get_file_id(message),
        "file_unique_id": _get_file_unique_id(message),
        "file_name": _get_file_name(message),
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _get_file_id(message: Message) -> str | None:
    if message.photo:
        return message.photo[-1].file_id

    for attribute in (
        "video",
        "document",
        "audio",
        "voice",
        "sticker",
        "animation",
        "video_note",
    ):
        content = getattr(message, attribute)
        if content is not None:
            return content.file_id

    return None


def _get_file_unique_id(message: Message) -> str | None:
    if message.photo:
        return message.photo[-1].file_unique_id

    for attribute in (
        "video",
        "document",
        "audio",
        "voice",
        "sticker",
        "animation",
        "video_note",
    ):
        content = getattr(message, attribute)
        if content is not None:
            return content.file_unique_id

    return None


def _get_file_name(message: Message) -> str | None:
    for attribute in ("document", "audio", "video", "animation"):
        content = getattr(message, attribute)
        if content is not None:
            return content.file_name

    return None


async def _notify_admins(
    *,
    bot: Bot,
    message: Message,
    ticket_id: int | None,
    user: User,
) -> None:
    if ticket_id is None:
        return

    header = (
        "🆘 تیکت جدید پشتیبانی\n"
        f"شماره تیکت: #{ticket_id}\n"
        f"کاربر: {user.name}\n"
        f"Telegram ID: {user.telegram_id}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, header)
            await message.copy_to(chat_id=admin_id)
        except TelegramAPIError:
            logger.warning(
                "Could not deliver support ticket %s to admin %s",
                ticket_id,
                admin_id,
            )
