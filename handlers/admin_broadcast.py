import logging

from aiogram import F, Router
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
from services.broadcast import BroadcastService
from states.admin import AdminBroadcastStates
from validators.broadcast import validate_broadcast_message

router = Router()
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())

logger = logging.getLogger(__name__)

BROADCAST_SOURCE_CHAT_ID_KEY = "broadcast_source_chat_id"
BROADCAST_MESSAGE_ID_KEY = "broadcast_message_id"
RECIPIENT_COUNT_KEY = "recipient_count"
PROGRESS_UPDATE_INTERVAL = 10


@router.message(F.text == "📢 ارسال همگانی")
async def broadcast_start_handler(
    message: Message,
    state: FSMContext,
    broadcast_service: BroadcastService,
) -> None:
    await state.set_state(AdminBroadcastStates.waiting_message)
    recipient_count = await broadcast_service.count_recipients()
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
async def broadcast_message_handler(message: Message, state: FSMContext) -> None:
    if not validate_broadcast_message(message):
        await message.answer(
            "❌ این نوع پیام برای ارسال همگانی پشتیبانی نمی‌شود.\n"
            "یک متن، عکس، ویدیو، فایل، صوت، ویس، استیکر، گیف یا ویدیو مسیج ارسال کنید."
        )
        return

    await state.update_data(
        **{
            BROADCAST_SOURCE_CHAT_ID_KEY: message.chat.id,
            BROADCAST_MESSAGE_ID_KEY: message.message_id,
        }
    )

    data = await state.get_data()
    recipient_count = data.get(RECIPIENT_COUNT_KEY, 0)
    await state.set_state(AdminBroadcastStates.waiting_confirmation)

    await message.copy_to(
        chat_id=message.chat.id,
        reply_markup=ReplyKeyboardRemove(),
    )
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
        "می‌توانید متن، عکس، ویدیو، فایل، صوت، ویس، استیکر، گیف یا ویدیو مسیج ارسال کنید.",
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
    broadcast_service: BroadcastService,
) -> None:
    data = await state.get_data()
    from_chat_id = data.get(BROADCAST_SOURCE_CHAT_ID_KEY)
    message_id = data.get(BROADCAST_MESSAGE_ID_KEY)

    if from_chat_id is None or message_id is None:
        await state.clear()
        await callback.message.edit_text("❌ پیام یافت نشد. لطفاً دوباره تلاش کنید.")
        await callback.answer()
        return

    await state.clear()
    await callback.answer("📢 ارسال همگانی شروع شد.")

    recipient_count = await broadcast_service.count_recipients()
    if recipient_count == 0:
        await callback.message.edit_text("❌ هیچ کاربر فعالی برای ارسال پیام وجود ندارد.")
        return

    await callback.message.edit_text(
        _progress_text(0, recipient_count, 0, 0),
    )

    last_progress: tuple[int, int, int, int] | None = None

    async def update_progress(
        processed: int,
        total: int,
        success: int,
        failed: int,
    ) -> None:
        nonlocal last_progress
        current = (processed, total, success, failed)
        if current == last_progress:
            return
        last_progress = current
        try:
            await callback.message.edit_text(*[_progress_text(*current)])
        except TelegramAPIError as exc:
            logger.warning("Failed to update broadcast progress: %s", exc)

    result = await broadcast_service.broadcast(
        from_chat_id=from_chat_id,
        message_id=message_id,
        progress_callback=update_progress,
        progress_interval=PROGRESS_UPDATE_INTERVAL,
    )

    await callback.message.edit_text(
        "📢 ارسال همگانی پایان یافت\n\n"
        f"👥 کل کاربران هدف: {result.total}\n"
        f"✅ ارسال موفق: {result.success}\n"
        f"❌ ناموفق: {result.failed}\n"
        f"⏱ مدت زمان: {result.duration_seconds} ثانیه"
    )


def _progress_text(processed: int, total: int, success: int, failed: int) -> str:
    return (
        "📢 ارسال همگانی در حال انجام است...\n\n"
        f"ارسال شده: {processed} / {total}\n"
        f"موفق: {success}\n"
        f"ناموفق: {failed}"
    )
