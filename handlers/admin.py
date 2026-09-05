from math import ceil

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from callbacks.admin import (
    AdminBlockedUsersCallback,
    AdminStatsCallback,
    AdminStatsRefreshCallback,
    AdminUserActionCallback,
    AdminUserCallback,
    AdminUsersCallback,
)
from exceptions.user import UserNotFoundError
from filters.admin import AdminFilter, AdminPermissionFilter
from keyboards.admin import build_admin_menu
from keyboards.admin_cancel import admin_cancel_keyboard
from keyboards.admin_stats import (
    antispam_stats_keyboard,
    broadcast_stats_keyboard,
    placeholder_stats_keyboard,
    stats_dashboard_keyboard,
    support_stats_keyboard,
    user_stats_keyboard,
)
from keyboards.admin_user_actions import user_actions_keyboard
from keyboards.admin_users import (
    blocked_users_keyboard,
    user_management_keyboard,
    users_keyboard,
)
from models.user import User, UserStatus
from services.admin import AdminService
from services.antispam import AntiSpamService
from services.broadcast import BroadcastService
from services.notification import NotificationService
from services.support import SupportService
from services.user import UserService
from states.admin import AdminUserStates

router = Router()
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())

_PAGE_SIZE = 5


@router.message(Command("admin"))
async def admin_handler(
    message: Message,
    state: FSMContext,
    admin_service: AdminService,
) -> None:
    await state.clear()
    permissions = await admin_service.get_effective_permissions(message.from_user.id)
    await message.answer(
        "👨‍💼 پنل مدیریت\n\nیکی از گزینه‌ها را انتخاب کنید:",
        reply_markup=build_admin_menu(permissions),
    )


@router.message(F.text == "👤 کاربران", AdminPermissionFilter("users"))
async def user_management_handler(message: Message) -> None:
    await _show_user_management(message=message)


@router.callback_query(
    F.data == "admin_user_management",
    AdminPermissionFilter("users"),
)
async def user_management_callback_handler(callback: CallbackQuery) -> None:
    await _show_user_management(message=callback.message, edit=True)
    await callback.answer()


@router.callback_query(
    F.data == "admin_browse_users",
    AdminPermissionFilter("users"),
)
async def browse_users_start_handler(
    callback: CallbackQuery,
    user_service: UserService,
) -> None:
    await _show_users_page(
        message=callback.message,
        user_service=user_service,
        page=0,
        edit=True,
    )
    await callback.answer()


@router.callback_query(F.data == "admin_find_user", AdminPermissionFilter("users"))
async def find_user_start_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.set_state(AdminUserStates.waiting_for_user_id)
    await callback.message.edit_text(
        "🔎 شناسه تلگرام کاربر را ارسال کنید:",
        reply_markup=admin_cancel_keyboard,
    )
    await callback.answer()


@router.message(F.text == "📊 آمار", AdminPermissionFilter("stats"))
async def stats_dashboard_handler(message: Message) -> None:
    await _show_stats_dashboard(message=message, edit=False)


@router.callback_query(
    AdminStatsCallback.filter(F.section == "dashboard"),
    AdminPermissionFilter("stats"),
)
async def stats_dashboard_callback_handler(
    callback: CallbackQuery,
) -> None:
    await _show_stats_dashboard(message=callback.message, edit=True)
    await callback.answer()


@router.callback_query(
    AdminStatsCallback.filter(F.section == "users"),
    AdminPermissionFilter("stats"),
)
async def user_stats_handler(
    callback: CallbackQuery,
    user_service: UserService,
) -> None:
    await _show_user_statistics(
        message=callback.message,
        user_service=user_service,
    )
    await callback.answer()


@router.callback_query(
    AdminStatsCallback.filter(F.section == "support"),
    AdminPermissionFilter("stats"),
)
async def support_stats_handler(
    callback: CallbackQuery,
    support_service: SupportService,
) -> None:
    await _show_support_statistics(
        message=callback.message,
        support_service=support_service,
    )
    await callback.answer()


@router.callback_query(
    AdminStatsCallback.filter(F.section == "broadcast"),
    AdminPermissionFilter("stats"),
)
async def broadcast_stats_handler(
    callback: CallbackQuery,
    broadcast_service: BroadcastService,
) -> None:
    await _show_broadcast_statistics(
        message=callback.message,
        broadcast_service=broadcast_service,
    )
    await callback.answer()


@router.callback_query(
    AdminStatsCallback.filter(F.section == "antispam"),
    AdminPermissionFilter("stats"),
)
async def antispam_stats_handler(
    callback: CallbackQuery,
    antispam_service: AntiSpamService,
) -> None:
    await _show_antispam_statistics(
        message=callback.message,
        antispam_service=antispam_service,
    )
    await callback.answer()


@router.callback_query(AdminStatsRefreshCallback.filter(), AdminPermissionFilter("stats"))
async def stats_refresh_handler(
    callback: CallbackQuery,
    callback_data: AdminStatsRefreshCallback,
    user_service: UserService,
    support_service: SupportService,
    broadcast_service: BroadcastService,
    antispam_service: AntiSpamService,
) -> None:
    section = callback_data.section

    if section == "dashboard":
        await _show_stats_dashboard(message=callback.message, edit=True)
    elif section == "users":
        await _show_user_statistics(
            message=callback.message,
            user_service=user_service,
        )
    elif section == "support":
        await _show_support_statistics(
            message=callback.message,
            support_service=support_service,
        )
    elif section == "broadcast":
        await _show_broadcast_statistics(
            message=callback.message,
            broadcast_service=broadcast_service,
        )
    elif section == "antispam":
        await _show_antispam_statistics(
            message=callback.message,
            antispam_service=antispam_service,
        )
    else:
        await _show_placeholder_statistics(
            message=callback.message,
            section=section,
        )

    await callback.answer("بروزرسانی شد.")
