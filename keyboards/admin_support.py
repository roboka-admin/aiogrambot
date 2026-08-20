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
                        status=SupportStatus.OPEN.value,
                        page=0,
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text=f"⚪ بسته ({closed_count})",
                    callback_data=AdminSupportListCallback(
                        status=SupportStatus.CLOSED.value,
                        page=0,
                    ).pack(),
                ),
            ],
        ]
    )


def support_tickets_keyboard(
    *,
    tickets: list[SupportTicket],
    status: SupportStatus,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for ticket in tickets:
        builder.button(
            text=f"🎫 #{ticket.id} | {ticket.user_telegram_id}",
            callback_data=AdminSupportTicketCallback(
                ticket_id=ticket.id or 0,
                status=status.value,
                page=page,
            ).pack(),
        )

    builder.adjust(1)

    navigation: list[InlineKeyboardButton] = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text="⬅️ قبلی",
                callback_data=AdminSupportListCallback(
                    status=status.value,
                    page=page - 1,
                ).pack(),
            )
        )
    if page < total_pages - 1:
        navigation.append(
            InlineKeyboardButton(
                text="بعدی ➡️",
                callback_data=AdminSupportListCallback(
                    status=status.value,
                    page=page + 1,
                ).pack(),
            )
        )
    if navigation:
        builder.row(*navigation)

    builder.button(
        text="⬅️ بازگشت",
        callback_data=AdminSupportBackCallback().pack(),
    )
    return builder.as_markup()


def support_ticket_keyboard(
    *,
    status: SupportStatus,
    page: int,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ بازگشت به تیکت‌ها",
                    callback_data=AdminSupportListCallback(
                        status=status.value,
                        page=page,
                    ).pack(),
                )
            ]
        ]
    )
