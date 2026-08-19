from math import ceil

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from callbacks.admin import (
    AdminUserActionCallback,
    AdminUserCallback,
    AdminUsersCallback,
)
from filters.admin import AdminFilter
from keyboards.admin import admin_menu
from keyboards.admin_user_actions import user_actions_keyboard
from keyboards.admin_users import users_keyboard
from services.user import UserService


router = Router()
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())

_PAGE_SIZE = 5


@router.message(Command("admin"))
async def admin_handler(message: Message) -> None:
    await message.answer(
        "👨‍💼 پنل مدیریت\n\n"
        "یکی از گزینه‌ها را انتخاب کنید:",
        reply_markup=admin_menu,
    )


@router.message(F.text == "👤 کاربران")
async def users_handler(message: Message, user_service: UserService) -> None:
    await _show_users_page(message=message, user_service=user_service, page=0)


@router.callback_query(AdminUsersCallback.filter())
async def users_page_handler(
    callback: CallbackQuery,
    callback_data: AdminUsersCallback,
    user_service: UserService,
) -> None:
    await _show_users_page(
        message=callback.message,
        user_service=user_service,
        page=callback_data.page,
        edit=True,
    )
    await callback.answer()


@router.callback_query(AdminUserCallback.filter())
async def user_details_handler(
    callback: CallbackQuery,
    callback_data: AdminUserCallback,
    user_service: UserService,
) -> None:
    user = await user_service.get_user(callback_data.telegram_id)
    await callback.message.edit_text(
        _user_details_text(user),
        reply_markup=user_actions_keyboard(user),
    )
    await callback.answer()


@router.callback_query(AdminUserActionCallback.filter())
async def user_action_handler(
    callback: CallbackQuery,
    callback_data: AdminUserActionCallback,
    user_service: UserService,
) -> None:
    action = callback_data.action
    telegram_id = callback_data.telegram_id

    if action == "add_coin":
        user = await user_service.add_coins(telegram_id)
        notice = "یک سکه اضافه شد."
    elif action == "remove_coin":
        user = await user_service.remove_coins(telegram_id)
        notice = "یک سکه کم شد."
    elif action == "add_warning":
        user = await user_service.add_warning(telegram_id)
        notice = "یک اخطار اضافه شد."
    elif action == "block":
        user = await user_service.block_user(telegram_id)
        notice = "کاربر مسدود شد."
    elif action == "unblock":
        user = await user_service.unblock_user(telegram_id)
        notice = "کاربر رفع مسدودیت شد."
    else:
        await callback.answer("عملیات نامعتبر است.", show_alert=True)
        return

    await callback.message.edit_text(
        _user_details_text(user),
        reply_markup=user_actions_keyboard(user),
    )
    await callback.answer(notice)


@router.callback_query(F.data == "noop")
async def noop_handler(callback: CallbackQuery) -> None:
    await callback.answer()


async def _show_users_page(
    *,
    message: Message,
    user_service: UserService,
    page: int,
    edit: bool = False,
) -> None:
    users, total, page = await user_service.get_users_page(
        page=page,
        page_size=_PAGE_SIZE,
    )

    if total == 0:
        text = "👤 کاربران\n\nهنوز کاربری ثبت‌نام نکرده است."
        if edit:
            await message.edit_text(text)
        else:
            await message.answer(text)
        return

    total_pages = ceil(total / _PAGE_SIZE)
    text = (
        "👤 کاربران\n\n"
        f"تعداد کل کاربران: {total}\n"
        "برای مشاهده اطلاعات هر کاربر، روی نام او بزنید."
    )
    keyboard = users_keyboard(
        users=users,
        page=page,
        total_pages=total_pages,
    )

    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


def _user_details_text(user) -> str:
    return (
        "👤 اطلاعات کاربر\n\n"
        f"نام: {user.name}\n"
        f"سن: {user.age}\n"
        f"شناسه: {user.telegram_id}\n"
        f"سکه: {user.coins}\n"
        f"اخطار: {user.warnings}\n"
        f"وضعیت: {user.status.value}"
    )
