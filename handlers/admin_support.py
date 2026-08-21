import json
from html import escape
from math import ceil

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from callbacks.admin_support import (
    AdminSupportActionCallback,
    AdminSupportBackCallback,
    AdminSupportListCallback,
    AdminSupportTicketCallback,
    AdminSupportUserCallback,
)
from exceptions.user import UserNotFoundError
from filters.admin import AdminFilter
from keyboards.admin_support import (
    support_overview_keyboard,
    support_user_messages_keyboard,
    support_users_keyboard,
)
from models.support import SupportStatus, SupportTicket, SupportUserSummary
from services.support import SupportService
from services.user import UserService
from states.admin_support import AdminSupportStates


router = Router()
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())
PAGE_SIZE = 10


@router.message(F.text == "📩 پشتیبانی")
async def admin_support_handler(message: Message, support_service: SupportService) -> None:
    await _show_support_overview(message=message, support_service=support_service)


@router.callback_query(AdminSupportListCallback.filter())
async def support_user_list_handler(callback: CallbackQuery, callback_data: AdminSupportListCallback, support_service: SupportService, user_service: UserService) -> None:
    status = SupportStatus(callback_data.status)
    users = await support_service.get_support_users_by_status(status)
    page_items, total_pages, page = _paginate(users, callback_data.page)
    status_text = "باز" if status is SupportStatus.OPEN else "بسته"
    names = await _user_names(page_items, user_service)
    await callback.message.edit_text(
        f"📩 کاربران دارای تیکت {status_text}\n\nتعداد کاربران: {len(users)}\nصفحه {page + 1} از {total_pages}\n\nهر کاربر را برای مشاهده پیام‌هایش انتخاب کنید.",
        reply_markup=_support_users_keyboard_with_names(page_items, names, status, page, total_pages),
    )
    await callback.answer()


@router.callback_query(AdminSupportUserCallback.filter())
async def support_user_messages_handler(callback: CallbackQuery, callback_data: AdminSupportUserCallback, support_service: SupportService, user_service: UserService) -> None:
    await _show_user_conversation(
        message=callback.message,
        telegram_id=callback_data.telegram_id,
        status=SupportStatus(callback_data.status),
        page=callback_data.page,
        support_service=support_service,
        user_service=user_service,
    )
    await callback.answer()


@router.callback_query(AdminSupportTicketCallback.filter())
async def support_ticket_detail_handler(
    callback: CallbackQuery,
    callback_data: AdminSupportTicketCallback,
    support_service: SupportService,
    bot: Bot,
) -> None:
    status = SupportStatus(callback_data.status)
    ticket = await support_service.get_ticket(callback_data.ticket_id)

    if (
        ticket is None
        or ticket.user_telegram_id != callback_data.telegram_id
        or ticket.status is not status
    ):
        await callback.answer("❌ این تیکت در دسترس نیست.", show_alert=True)
        return

    try:
        await _send_ticket_content(
            bot=bot,
            chat_id=callback.message.chat.id,
            ticket=ticket,
        )
    except (TelegramAPIError, ValueError):
        await callback.message.answer("❌ نمایش محتوای این تیکت ممکن نیست.")

    await callback.answer()


@router.callback_query(AdminSupportActionCallback.filter(F.action == "reply"))
async def start_support_reply_handler(callback: CallbackQuery, callback_data: AdminSupportActionCallback, state: FSMContext) -> None:
    await state.set_state(AdminSupportStates.waiting_reply)
    await state.update_data(
        telegram_id=callback_data.telegram_id,
        status=callback_data.status,
        page=callback_data.page,
    )
    await callback.answer()
    await callback.message.answer(
        "✉️ پاسخ خود را برای کاربر ارسال کنید.\n"
        "می‌توانید متن، عکس، ویدیو، فایل، صوت، ویس، استیکر، گیف یا ویدیو مسیج ارسال کنید.\n\n"
        "برای لغو، دکمه «❌ لغو» را ارسال کنید."
    )


@router.message(AdminSupportStates.waiting_reply, F.text == "❌ لغو")
async def cancel_support_reply_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("ارسال پاسخ لغو شد.")


@router.message(AdminSupportStates.waiting_reply)
async def send_support_reply_handler(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    telegram_id = data.get("telegram_id")
    if not isinstance(telegram_id, int):
        await state.clear()
        await message.answer("❌ اطلاعات گفتگو نامعتبر است.")
        return

    try:
        await bot.send_message(telegram_id, "✉️ پاسخ پشتیبانی:")
        await message.copy_to(chat_id=telegram_id)
    except TelegramAPIError:
        await message.answer("❌ ارسال پاسخ به کاربر ممکن نشد. ممکن است کاربر ربات را مسدود کرده باشد.")
        return

    await state.clear()
    await message.answer("✅ پاسخ با موفقیت برای کاربر ارسال شد.")


@router.callback_query(AdminSupportActionCallback.filter(F.action.in_({"close", "reopen"})))
async def change_support_conversation_status_handler(callback: CallbackQuery, callback_data: AdminSupportActionCallback, support_service: SupportService, user_service: UserService) -> None:
    if callback_data.action == "close":
        await support_service.close_user_conversation(callback_data.telegram_id)
        new_status = SupportStatus.CLOSED
        result_text = "🔒 گفتگو بسته شد."
    else:
        await support_service.reopen_user_conversation(callback_data.telegram_id)
        new_status = SupportStatus.OPEN
        result_text = "🟢 گفتگو دوباره باز شد."

    await _show_user_conversation(
        message=callback.message,
        telegram_id=callback_data.telegram_id,
        status=new_status,
        page=callback_data.page,
        support_service=support_service,
        user_service=user_service,
    )
    await callback.answer(result_text)


@router.callback_query(AdminSupportBackCallback.filter())
async def support_back_handler(callback: CallbackQuery, support_service: SupportService) -> None:
    await _show_support_overview(message=callback.message, support_service=support_service, edit=True)
    await callback.answer()


async def _show_user_conversation(*, message: Message, telegram_id: int, status: SupportStatus, page: int, support_service: SupportService, user_service: UserService) -> None:
    tickets = await support_service.get_user_tickets_by_status(telegram_id, status)
    try:
        user = await user_service.get_user(telegram_id)
        user_name = escape(user.name)
        user_text = f'<a href="tg://user?id={telegram_id}">{user_name}</a>'
    except UserNotFoundError:
        user_text = "کاربر پیدا نشد"

    status_text = "🟢 باز" if status is SupportStatus.OPEN else "⚪ بسته"
    await message.edit_text(
        f"👤 کاربر: {user_text}\n"
        f"🆔 <code>{telegram_id}</code>\n"
        f"📌 وضعیت گفتگو: {status_text}\n"
        f"📩 تعداد پیام‌ها: {len(tickets)}\n\n"
        "برای مشاهده محتوای هر پیام، شماره تیکت را انتخاب کنید.",
        reply_markup=support_user_messages_keyboard(
            telegram_id=telegram_id,
            status=status,
            page=page,
            tickets=tickets,
        ),
        parse_mode="HTML",
    )


async def _show_support_overview(*, message: Message, support_service: SupportService, edit: bool = False) -> None:
    open_users = await support_service.get_support_users_by_status(SupportStatus.OPEN)
    closed_users = await support_service.get_support_users_by_status(SupportStatus.CLOSED)
    text = f"📩 مدیریت پشتیبانی\n\n🟢 کاربران با پیام باز: {len(open_users)}\n⚪ کاربران با پیام بسته: {len(closed_users)}\n\nیک بخش را انتخاب کنید:"
    keyboard = support_overview_keyboard(open_count=len(open_users), closed_count=len(closed_users))
    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


def _paginate(items: list[SupportUserSummary], requested_page: int) -> tuple[list[SupportUserSummary], int, int]:
    total_pages = max(1, ceil(len(items) / PAGE_SIZE))
    page = min(max(requested_page, 0), total_pages - 1)
    start = page * PAGE_SIZE
    return items[start:start + PAGE_SIZE], total_pages, page


async def _user_names(users: list[SupportUserSummary], user_service: UserService) -> dict[int, str]:
    names = {}
    for summary in users:
        try:
            names[summary.user_telegram_id] = (await user_service.get_user(summary.user_telegram_id)).name
        except UserNotFoundError:
            names[summary.user_telegram_id] = str(summary.user_telegram_id)
    return names


def _support_users_keyboard_with_names(users: list[SupportUserSummary], names: dict[int, str], status: SupportStatus, page: int, total_pages: int):
    keyboard = support_users_keyboard(users=users, status=status, page=page, total_pages=total_pages)
    for row, summary in zip(keyboard.inline_keyboard[:len(users)], users):
        row[0].text = f"👤 {names[summary.user_telegram_id]} | 📩 {summary.ticket_count}"
    return keyboard


async def _send_ticket_content(*, bot: Bot, chat_id: int, ticket: SupportTicket) -> None:
    payload = _deserialize_message(ticket.message)
    content_type = payload["content_type"]
    text = payload.get("text") or ""
    caption = payload.get("caption") or None
    file_id = payload.get("file_id")

    if content_type == "text":
        await bot.send_message(chat_id, text or "بدون متن")
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
        raise ValueError("Unsupported or incomplete support ticket payload")


def _deserialize_message(message: str) -> dict[str, str]:
    try:
        payload = json.loads(message)
    except json.JSONDecodeError:
        return {"content_type": "text", "text": message}
    if not isinstance(payload, dict):
        return {"content_type": "unknown", "text": message}
    return {
        "content_type": str(payload.get("content_type") or "unknown"),
        "text": str(payload.get("text") or ""),
        "caption": str(payload.get("caption") or ""),
        "file_id": str(payload.get("file_id") or ""),
    }
