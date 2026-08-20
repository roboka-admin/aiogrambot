from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from callbacks.admin_support import (
    AdminSupportBackCallback,
    AdminSupportListCallback,
    AdminSupportTicketCallback,
)
from models.support import SupportStatus, SupportTicket


def support_overview_keyboard(
    *,
    open_count: int,
    closed_count: int,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🟢 باز ({open_count})",
                    callback_data=AdminSupportListCallback(
                        status=SupportStatus.OPEN.value
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text=f"⚪ بسته ({closed_count})",
                    callback_data=AdminSupportListCallback(
                        status=SupportStatus.CLOSED.value
                    ).pack(),
                ),
            ],
        ]
    )


def support_tickets_keyboard(
    *,
    tickets: list[SupportTicket],
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for ticket in tickets:
        builder.button(
            text=f"🎫 #{ticket.id} | {ticket.user_telegram_id}",
            callback_data=AdminSupportTicketCallback(
                ticket_id=ticket.id or 0
            ).pack(),
        )

    builder.adjust(1)
    builder.button(
        text="⬅️ بازگشت",
        callback_data=AdminSupportBackCallback().pack(),
    )
    return builder.as_markup()


def support_ticket_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ بازگشت به تیکت‌ها",
                    callback_data=AdminSupportBackCallback().pack(),
                )
            ]
        ]
    )
