from math import ceil

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from callbacks.admin import AdminBlockedUsersCallback, AdminUserActionCallback, AdminUserCallback, AdminUsersCallback
from exceptions.user import UserNotFoundError
from filters.admin import AdminFilter, AdminPermissionFilter
from keyboards.admin_cancel import admin_cancel_keyboard
from keyboards.admin_user_actions import user_actions_keyboard
from keyboards.admin_users import blocked_users_keyboard, user_management_keyboard, users_keyboard
from models.user import UserStatus
from services.admin import AdminService
from services.notification import NotificationService
from services.user import UserService
from states.admin import AdminUserStates

router = Router()
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())

_PAGE_SIZE = 5


async def _show_user_management(message: Message, *, edit: bool = False) -> None:
    text = "👤 مدیریت کاربران\n\nیکی از گزینه‌ها را انتخاب کنید:"
    if edit:
        await message.edit_text(text, reply_markup=user_management_keyboard())
    else:
        await message.answer(text, reply_markup=user_management_keyboard())


async def _show_users_page(
    message: Message,
    user_service: UserService,
    *,
    page: int,
    edit: bool = False,
) -> None:
    users, total, page = await user_service.get_users_page(page=page, page_size=_PAGE_SIZE)
    total_pages = max(1, ceil(total / _PAGE_SIZE))
    text = f"👥 کاربران\n\nتعداد کل: {total}\nصفحه {page + 1} از {total_pages}"
    markup = users_keyboard(users=users, page=page, total_pages=total_pages)
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


async def _show_blocked_users_page(
    message: Message,
    user_service: UserService,
    *,
    page: int,
    edit: bool = False,
) -> None:
    users, total, page = await user_service.get_blocked_users_page(
        page=page, page_size=_PAGE_SIZE
    )
    total_pages = max(1, ceil(total / _PAGE_SIZE))
    text = f"🚫 کاربران مسدود\n\nتعداد: {total}\nصفحه {page + 1} از {total_pages}"
    markup = blocked_users_keyboard(users=users, page=page, total_pages=total_pages)
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


async def _show_user(
    callback: CallbackQuery,
    user_service: UserService,
    *,
    telegram_id: int,
    source: str,
    page: int,
) -> None:
    try:
        user = await user_service.get_user(telegram_id)
    except UserNotFoundError:
        await callback.answer("کاربر پیدا نشد.", show_alert=True)
        return

    status = "مسدود" if user.status is UserStatus.BLOCKED else "فعال"
    text = (
        f"👤 اطلاعات کاربر\n\n"
        f"شناسه: {user.telegram_id}\n"
        f"نام: {user.name or user.telegram_name or 'بدون نام'}\n"
        f"نام کاربری: @{user.username if user.username else 'ندارد'}\n"
        f"وضعیت: {status}\n"
        f"🪙 سکه: {user.coins}\n"
        f"⚠️ اخطار: {user.warnings}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=user_actions_keyboard(user, source=source, page=page),
    )
    await callback.answer()


@router.message(F.text == "👤 کاربران", AdminPermissionFilter("users"))
async def user_management_handler(message: Message) -> None:
    await _show_user_management(message=message)


@router.callback_query(F.data == "admin_user_management", AdminPermissionFilter("users"))
async def user_management_callback_handler(callback: CallbackQuery) -> None:
    await _show_user_management(message=callback.message, edit=True)
    await callback.answer()


@router.callback_query(F.data == "admin_browse_users", AdminPermissionFilter("users"))
async def browse_users_start_handler(callback: CallbackQuery, user_service: UserService) -> None:
    await _show_users_page(callback.message, user_service, page=0, edit=True)
    await callback.answer()


@router.callback_query(F.data == "admin_blocked_users", AdminPermissionFilter("users"))
async def blocked_users_start_handler(callback: CallbackQuery, user_service: UserService) -> None:
    await _show_blocked_users_page(callback.message, user_service, page=0, edit=True)
    await callback.answer()


@router.callback_query(AdminUsersCallback.filter(), AdminPermissionFilter("users"))
async def users_page_handler(
    callback: CallbackQuery,
    callback_data: AdminUsersCallback,
    user_service: UserService,
) -> None:
    await _show_users_page(callback.message, user_service, page=callback_data.page, edit=True)
    await callback.answer()


@router.callback_query(AdminBlockedUsersCallback.filter(), AdminPermissionFilter("users"))
async def blocked_users_page_handler(
    callback: CallbackQuery,
    callback_data: AdminBlockedUsersCallback,
    user_service: UserService,
) -> None:
    await _show_blocked_users_page(
        callback.message, user_service, page=callback_data.page, edit=True
    )
    await callback.answer()


@router.callback_query(AdminUserCallback.filter(), AdminPermissionFilter("users"))
async def user_view_handler(
    callback: CallbackQuery,
    callback_data: AdminUserCallback,
    user_service: UserService,
) -> None:
    await _show_user(
        callback,
        user_service,
        telegram_id=callback_data.telegram_id,
        source=callback_data.source,
        page=callback_data.page,
    )


@router.callback_query(AdminUserActionCallback.filter(), AdminPermissionFilter("users"))
async def user_action_handler(
    callback: CallbackQuery,
    callback_data: AdminUserActionCallback,
    user_service: UserService,
    notification_service: NotificationService,
) -> None:
    try:
        if callback_data.action == "add_coin":
            user = await user_service.add_coins(callback_data.telegram_id)
            await notification_service.coins_added(user.telegram_id, 1, user.coins)
            message = "یک سکه اضافه شد."
        elif callback_data.action == "remove_coin":
            user = await user_service.remove_coins(callback_data.telegram_id)
            await notification_service.coins_removed(user.telegram_id, 1, user.coins)
            message = "یک سکه کم شد."
        elif callback_data.action == "add_warning":
            user = await user_service.add_warning(callback_data.telegram_id)
            if user.status is UserStatus.BLOCKED:
                await notification_service.user_auto_blocked(user.telegram_id)
                message = "اخطار ثبت شد و کاربر به حد مسدودی رسید."
            else:
                await notification_service.warning_added(user.telegram_id, user.warnings)
                message = "اخطار ثبت شد."
        elif callback_data.action == "block":
            user = await user_service.block_user(callback_data.telegram_id)
            await notification_service.user_blocked(user.telegram_id)
            message = "کاربر مسدود شد."
        elif callback_data.action == "unblock":
            user = await user_service.unblock_user(callback_data.telegram_id)
            await notification_service.user_unblocked(user.telegram_id)
            message = "رفع مسدودیت انجام شد."
        else:
            await callback.answer("عملیات نامعتبر است.", show_alert=True)
            return
    except UserNotFoundError:
        await callback.answer("کاربر پیدا نشد.", show_alert=True)
        return

    await _show_user(
        callback,
        user_service,
        telegram_id=callback_data.telegram_id,
        source=callback_data.source,
        page=callback_data.page,
    )
    await callback.answer(message)


@router.callback_query(F.data == "admin_find_user", AdminPermissionFilter("users"))
async def find_user_start_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminUserStates.waiting_for_user_id)
    await callback.message.edit_text("🔎 شناسه تلگرام کاربر را ارسال کنید:", reply_markup=admin_cancel_keyboard)
    await callback.answer()


@router.message(AdminUserStates.waiting_for_user_id, AdminPermissionFilter("users"))
async def find_user_handler(message: Message, state: FSMContext, user_service: UserService) -> None:
    if not message.text or not message.text.strip().isdigit() or int(message.text.strip()) <= 0:
        await message.answer("❌ شناسه باید یک عدد معتبر باشد. دوباره ارسال کنید.")
        return
    try:
        user = await user_service.get_user(int(message.text.strip()))
    except UserNotFoundError:
        await message.answer("❌ کاربر پیدا نشد. شناسه را بررسی کنید.")
        return
    await state.clear()
    status = "مسدود" if user.status is UserStatus.BLOCKED else "فعال"
    await message.answer(
        f"👤 اطلاعات کاربر\n\nشناسه: {user.telegram_id}\nنام: {user.name or user.telegram_name or 'بدون نام'}\nوضعیت: {status}\n🪙 سکه: {user.coins}\n⚠️ اخطار: {user.warnings}",
        reply_markup=user_actions_keyboard(user, source="users", page=0),
    )
