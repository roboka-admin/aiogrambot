import json
from html import escape

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from callbacks.admin_support import (
    AdminSupportBackCallback,
    AdminSupportListCallback,
    AdminSupportTicketCallback,
)
from exceptions.user import UserNotFoundError
from filters.admin import AdminFilter
from keyboards.admin_support import (
    support_overview_keyboard,
    support_ticket_keyboard,
    support_tickets_keyboard,
)
from models.support import SupportStatus, SupportTicket
from services.support import SupportService
from services.user import UserService


router = Router()
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())


@router.message(F.text == "📩 پشتیبانی")
async def admin_support_handler(
    message: Message,
    support_service: SupportService,
) -> None:
    await _show_support_overview(
        message=message,
        support_service=support_service,
    )


@router.callback_query(AdminSupportListCallback.filter())
async def support_ticket_list_handler(
    callback: CallbackQuery,
    callback_data: AdminSupportListCallback,
    support_service: SupportService,
) -> None:
    status = SupportStatus(callback_data.status)
    tickets = await support_service.get_tickets_by_status(status)
    status_text = "باز" if status is SupportStatus.OPEN else "بسته"

    text = f"📩 تیکت‌های {status_text}\n\n"
    if not tickets:
        text += "تیکتی در این بخش وجود ندارد."
    else:
        text += "برای مشاهده جزئیات، یک تیکت را انتخاب کنید."

    await callback.message.edit_text(
        text,
        reply_markup=support_tickets_keyboard(tickets=tickets),
    )
    await callback.answer()


@router.callback_query(AdminSupportTicketCallback.filter())
async def support_ticket_details_handler(
    callback: CallbackQuery,
    callback_data: AdminSupportTicketCallback,
    support_service: SupportService,
    user_service: UserService,
) -> None:
    ticket = await support_service.get_ticket(callback_data.ticket_id)
    if ticket is None:
        await callback.answer("تیکت پیدا نشد.", show_alert=True)
        return

    await callback.message.edit_text(
        await _ticket_details_text(
            ticket=ticket,
            user_service=user_service,
        ),
        reply_markup=support_ticket_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(AdminSupportBackCallback.filter())
async def support_back_handler(
    callback: CallbackQuery,
    support_service: SupportService,
) -> None:
    await _show_support_overview(
        message=callback.message,
        support_service=support_service,
        edit=True,
    )
    await callback.answer()


async def _show_support_overview(
    *,
    message: Message,
    support_service: SupportService,
    edit: bool = False,
) -> None:
    open_tickets = await support_service.get_tickets_by_status(
        SupportStatus.OPEN
    )
    closed_tickets = await support_service.get_tickets_by_status(
        SupportStatus.CLOSED
    )

    text = (
        "📩 مدیریت پشتیبانی\n\n"
        f"🟢 تیکت‌های باز: {len(open_tickets)}\n"
        f"⚪ تیکت‌های بسته: {len(closed_tickets)}\n\n"
        "یک بخش را انتخاب کنید:"
    )
    keyboard = support_overview_keyboard(
        open_count=len(open_tickets),
        closed_count=len(closed_tickets),
    )

    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


async def _ticket_details_text(
    *,
    ticket: SupportTicket,
    user_service: UserService,
) -> str:
    try:
        user = await user_service.get_user(ticket.user_telegram_id)
        user_name = escape(user.name)
        user_text = (
            f'<a href="tg://user?id={ticket.user_telegram_id}">'
            f"{user_name}</a>"
        )
    except UserNotFoundError:
        user_text = "کاربر پیدا نشد"

    payload = _deserialize_message(ticket.message)
    content_type = escape(payload.get("content_type", "unknown"))
    text = payload.get("text") or payload.get("caption") or "بدون متن"

    if len(text) > 1000:
        text = f"{text[:1000]}…"

    status_text = "🟢 باز" if ticket.status is SupportStatus.OPEN else "⚪ بسته"

    return (
        f"🎫 تیکت #{ticket.id}\n\n"
        f"👤 کاربر: {user_text}\n"
        f"🆔 شناسه: <code>{ticket.user_telegram_id}</code>\n"
        f"📌 وضعیت: {status_text}\n"
        f"📎 نوع محتوا: <code>{content_type}</code>\n\n"
        f"📝 پیام:\n{escape(text)}"
    )


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
    }
