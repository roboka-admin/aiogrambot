import json
from html import escape
from math import ceil

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from callbacks.admin_support import AdminSupportBackCallback, AdminSupportListCallback, AdminSupportUserCallback
from exceptions.user import UserNotFoundError
from filters.admin import AdminFilter
from keyboards.admin_support import support_overview_keyboard, support_user_messages_keyboard, support_users_keyboard
from models.support import SupportStatus, SupportTicket, SupportUserSummary
from services.support import SupportService
from services.user import UserService


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
    status = SupportStatus(callback_data.status)
    tickets = await support_service.get_user_tickets_by_status(callback_data.telegram_id, status)
    try:
        user = await user_service.get_user(callback_data.telegram_id)
        user_name = escape(user.name)
        user_text = f'<a href="tg://user?id={callback_data.telegram_id}">{user_name}</a>'
    except UserNotFoundError:
        user_text = "کاربر پیدا نشد"
    messages = "\n\n".join(_ticket_text(ticket) for ticket in tickets) or "پیامی وجود ندارد."
    if len(messages) > 3500:
        messages = f"{messages[:3500]}\n\n… پیام‌های بیشتر وجود دارد."
    await callback.message.edit_text(
        f"👤 کاربر: {user_text}\n🆔 <code>{callback_data.telegram_id}</code>\n📩 تعداد پیام‌ها: {len(tickets)}\n\n{messages}",
        reply_markup=support_user_messages_keyboard(status=status, page=callback_data.page),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(AdminSupportBackCallback.filter())
async def support_back_handler(callback: CallbackQuery, support_service: SupportService) -> None:
    await _show_support_overview(message=callback.message, support_service=support_service, edit=True)
    await callback.answer()


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


def _ticket_text(ticket: SupportTicket) -> str:
    payload = _deserialize_message(ticket.message)
    content_type = escape(payload.get("content_type", "unknown"))
    text = payload.get("text") or payload.get("caption") or "بدون متن"
    if len(text) > 800:
        text = f"{text[:800]}…"
    return f"🎫 <b>#{ticket.id}</b> | <code>{content_type}</code>\n{escape(text)}"


def _deserialize_message(message: str) -> dict[str, str]:
    try:
        payload = json.loads(message)
    except json.JSONDecodeError:
        return {"content_type": "text", "text": message}
    if not isinstance(payload, dict):
        return {"content_type": "unknown", "text": message}
    return {"content_type": str(payload.get("content_type") or "unknown"), "text": str(payload.get("text") or ""), "caption": str(payload.get("caption") or "")}
