import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from callbacks.admin import (
    AdminBroadcastCancelCallback,
    AdminBroadcastEditCallback,
    AdminBroadcastStartCallback,
)
from filters.admin import AdminFilter
from keyboards.admin_broadcast import broadcast_cancel_keyboard, broadcast_preview_keyboard
from services.user import UserService
from states.admin import AdminBroadcastStates


router = Router()
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())

logger = logging.getLogger(__name__)

# Key for storing broadcast message in FSM state data
BROADCAST_MESSAGE_KEY = "broadcast_message"
RECIPIENT_COUNT_KEY = "recipient_count"

# Progress update interval (in number of messages sent)
PROGRESS_UPDATE_INTERVAL = 10


@router.message(F.text == "📢 ارسال همگانی")
async def broadcast_start_handler(message: Message, state: FSMContext, user_service: UserService) -> None:
    await state.set_state(AdminBroadcastStates.waiting_message)

    recipient_count = len(await user_service.get_active_telegram_ids())
    await state.update_data(**{RECIPIENT_COUNT_KEY: recipient_count})

    await message.answer(
        "📢 پیام همگانی را ارسال کنید.\n"
        "می‌توانید متن، عکس، ویدیو، فایل، صوت، ویس، استیکر، گیف یا ویدیو مسیج ارسال کنید.",
        reply_markup=broadcast_cancel_keyboard(),
    )


@router.message(AdminBroadcastStates.waiting_message, F.text == "❌ لغو")
async def broadcast_cancel_text_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ ارسال همگانی لغو شد.", reply_markup=ReplyKeyboardRemove())


@router.message(AdminBroadcastStates.waiting_message)
async def broadcast_message_handler(message: Message, state: FSMContext, user_service: UserService) -> None:
    # Store message for preview
    await _store_broadcast_message(message, state)

    # Get recipient count
    data = await state.get_data()
    recipient_count = data.get(RECIPIENT_COUNT_KEY, 0)

    # Set state to waiting for confirmation
    await state.set_state(AdminBroadcastStates.waiting_confirmation)

    # Show preview
    await message.answer(
        f"📊 تعداد دریافت‌کنندگان: {recipient_count} کاربر\n"
        "آیا از ارسال این پیام مطمئن هستید؟",
        reply_markup=broadcast_preview_keyboard(),
    )


@router.callback_query(AdminBroadcastEditCallback.filter(), AdminBroadcastStates.waiting_confirmation)
async def broadcast_edit_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminBroadcastStates.waiting_message)
    await callback.message.edit_text(
        "✏️ پیام جدید را ارسال کنید.\n"
        "می‌توانید متن، عکس، ویدیو، فایل، صوت، ویس، استیکر، گیف یا ویدیو مسیج ارسال کنید."
    )
    await callback.answer()


@router.callback_query(AdminBroadcastCancelCallback.filter(), AdminBroadcastStates.waiting_confirmation)
async def broadcast_cancel_callback_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ ارسال همگانی لغو شد.")
    await callback.answer()


@router.callback_query(AdminBroadcastStartCallback.filter(), AdminBroadcastStates.waiting_confirmation)
async def broadcast_confirm_handler(
    callback: CallbackQuery,
    state: FSMContext,
    user_service: UserService,
    bot: Bot,
) -> None:
    data = await state.get_data()

    # Get stored message data
    message_data = data.get(BROADCAST_MESSAGE_KEY)
    if not message_data:
        await state.clear()
        await callback.message.edit_text("❌ پیام یافت نشد. لطفاً دوباره تلاش کنید.")
        await callback.answer()
        return

    # Clear state to prevent duplicate sends
    await state.clear()

    # Get recipients
    telegram_ids = await user_service.get_active_telegram_ids()
    total_count = len(telegram_ids)

    if total_count == 0:
        await callback.message.edit_text("❌ هیچ کاربر فعالی برای ارسال پیام وجود ندارد.")
        await callback.answer()
        return

    # Send initial progress message
    progress_message = await callback.message.edit_text(
        f"📢 ارسال همگانی در حال انجام است...\n\n"
        f"ارسال شده: 0 / {total_count}\n"
        f"موفق: 0\n"
        f"ناموفق: 0"
    )

    # Start broadcast
    success_count = 0
    fail_count = 0

    for index, telegram_id in enumerate(telegram_ids, start=1):
        try:
            await _send_broadcast_message(bot, telegram_id, message_data)
            success_count += 1
        except TelegramAPIError as e:
            fail_count += 1
            logger.warning("Failed to send broadcast to user %s: %s", telegram_id, e)
        except Exception as e:
            fail_count += 1
            logger.error("Unexpected error sending broadcast to user %s: %s", telegram_id, e)

        # Update progress periodically
        if index % PROGRESS_UPDATE_INTERVAL == 0 or index == total_count:
            try:
                await progress_message.edit_text(
                    f"📢 ارسال همگانی در حال انجام است...\n\n"
                    f"ارسال شده: {index} / {total_count}\n"
                    f"موفق: {success_count}\n"
                    f"ناموفق: {fail_count}"
                )
            except TelegramAPIError:
                pass  # Ignore if message wasn't modified

        # Small delay to avoid rate limiting
        await asyncio.sleep(0.05)

    # Send final result
    await progress_message.edit_text(
        f"✅ ارسال همگانی به پایان رسید.\n\n"
        f"کل کاربران: {total_count}\n"
        f"موفق: {success_count}\n"
        f"ناموفق: {fail_count}"
    )
    await callback.answer()


async def _store_broadcast_message(message: Message, state: FSMContext) -> None:
    """Store message data for later broadcast."""
    message_data = {
        "content_type": message.content_type.value,
        "text": message.text,
        "caption": message.caption,
        "file_id": _get_file_id(message),
        "file_unique_id": _get_file_unique_id(message),
        "file_name": _get_file_name(message),
    }
    await state.update_data(**{BROADCAST_MESSAGE_KEY: message_data})


def _get_file_id(message: Message) -> str | None:
    if message.photo:
        return message.photo[-1].file_id
    for attribute in ("video", "document", "audio", "voice", "sticker", "animation", "video_note"):
        content = getattr(message, attribute)
        if content is not None:
            return content.file_id
    return None


def _get_file_unique_id(message: Message) -> str | None:
    if message.photo:
        return message.photo[-1].file_unique_id
    for attribute in ("video", "document", "audio", "voice", "sticker", "animation", "video_note"):
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


async def _send_broadcast_message(bot: Bot, chat_id: int, message_data: dict) -> None:
    """Send the broadcast message to a user."""
    content_type = message_data["content_type"]
    text = message_data.get("text")
    caption = message_data.get("caption")
    file_id = message_data.get("file_id")

    if content_type == "text":
        await bot.send_message(chat_id, text or "")
    elif content_type == "photo" and file_id:
        await bot.send_photo(chat_id, file_id, caption=caption)
    elif content_type == "video" and file_id:
        await bot.send_video(chat_id, file_id, caption=caption)
    elif content_type == "document" and file_id:
        await bot.send_document(chat_id, file_id, caption=caption)
    elif content_type == "audio" and file_id:
        await bot.send_audio(chat_id, file_id, caption=caption)
    elif content_type == "voice" and file_id:
        await bot.send_voice(chat_id, file_id, caption=caption)
    elif content_type == "sticker" and file_id:
        await bot.send_sticker(chat_id, file_id)
    elif content_type == "animation" and file_id:
        await bot.send_animation(chat_id, file_id, caption=caption)
    elif content_type == "video_note" and file_id:
        await bot.send_video_note(chat_id, file_id)
    else:
        raise ValueError(f"Unsupported content type: {content_type}")
