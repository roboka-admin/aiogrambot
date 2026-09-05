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
from keyboards.admin_users import blocked_users_keyboard, user_management_keyboard, users_keyboard
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
async def admin_handler(message: Message, state: FSMContext, admin_service: AdminService) -> None:
    await state.clear()
    permissions = await admin_service.get_effective_permissions(message.from_user.id)
    await message.answer(
        "👨‍💼 پنل مدیریت\n\nیکی از گزینه‌ها را انتخاب کنید:",
        reply_markup=build_admin_menu(permissions),
    )


@router.message(F.text == "👤 کاربران", AdminPermissionFilter("users"))
async def user_management_handler(message: Message) -> None:
    await _show_user_management(message=message)


@router.callback_query(F.data == "admin_user_management", AdminPermissionFilter("users"))
async def user_management_callback_handler(callback: CallbackQuery) -> None:
    await _show_user_management(message=callback.message, edit=True)
    await callback.answer()


@router.callback_query(F.data == "admin_browse_users", AdminPermissionFilter("users"))
async def browse_users_start_handler(callback: CallbackQuery, user_service: UserService) -> None:
    await _show_users_page(message=callback.message, user_service=user_service, page=0, edit=True)
    await callback.answer()


@router.callback_query(F.data == "admin_find_user", AdminPermissionFilter("users"))
async def find_user_start_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminUserStates.waiting_for_user_id)
    await callback.message.edit_text(
        "🔎 شناسه تلگرام کاربر را ارسال کنید:",
        reply_markup=admin_cancel_keyboard,
    )
    await callback.answer()


@router.message(F.text == "📊 آمار", AdminPermissionFilter("stats"))
async def stats_dashboard_handler(message: Message) -> None:
    await _show_stats_dashboard(message=message, edit=False)


@router.callback_query(AdminStatsCallback.filter(F.section == "dashboard"), AdminPermissionFilter("stats"))
async def stats_dashboard_callback_handler(callback: CallbackQuery) -> None:
    await _show_stats_dashboard(message=callback.message, edit=True)
    await callback.answer()


@router.callback_query(AdminStatsCallback.filter(F.section == "users"), AdminPermissionFilter("stats"))
async def user_stats_handler(callback: CallbackQuery, user_service: UserService) -> None:
    await _show_user_statistics(message=callback.message, user_service=user_service)
    await callback.answer()


@router.callback_query(AdminStatsCallback.filter(F.section == "support"), AdminPermissionFilter("stats"))
async def support_stats_handler(callback: CallbackQuery, support_service: SupportService) -> None:
    await _show_support_statistics(message=callback.message, support_service=support_service)
    await callback.answer()


@router.callback_query(AdminStatsCallback.filter(F.section == "broadcast"), AdminPermissionFilter("stats"))
async def broadcast_stats_handler(callback: CallbackQuery, broadcast_service: BroadcastService) -> None:
    await _show_broadcast_statistics(message=callback.message, broadcast_service=broadcast_service)
    await callback.answer()


@router.callback_query(AdminStatsCallback.filter(F.section == "antispam"), AdminPermissionFilter("stats"))
async def antispam_stats_handler(callback: CallbackQuery, antispam_service: AntiSpamService) -> None:
    await _show_antispam_statistics(message=callback.message, antispam_service=antispam_service)
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
        await _show_user_statistics(message=callback.message, user_service=user_service)
    elif section == "support":
        await _show_support_statistics(message=callback.message, support_service=support_service)
    elif section == "broadcast":
        await _show_broadcast_statistics(message=callback.message, broadcast_service=broadcast_service)
    elif section == "antispam":
        await _show_antispam_statistics(message=callback.message, antispam_service=antispam_service)
    else:
        await _show_placeholder_statistics(message=callback.message, section=section)
    await callback.answer("بروزرسانی شد.")


@router.message(AdminUserStates.waiting_for_user_id, AdminPermissionFilter("users"))
async def find_user_handler(message: Message, state: FSMContext, user_service: UserService) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer(
            "❌ شناسه کاربر باید فقط شامل عدد باشد. دوباره ارسال کنید:",
            reply_markup=admin_cancel_keyboard,
        )
        return
    try:
        user = await user_service.get_user(int(text))
    except UserNotFoundError:
        await message.answer(
            "❌ کاربری با این شناسه پیدا نشد. دوباره تلاش کنید:",
            reply_markup=admin_cancel_keyboard,
        )
        return
    await state.clear()
    await message.answer(_user_details_text(user), reply_markup=user_actions_keyboard(user, source="management"))


@router.callback_query(AdminUsersCallback.filter(), AdminPermissionFilter("users"))
async def users_page_handler(callback: CallbackQuery, callback_data: AdminUsersCallback, user_service: UserService) -> None:
    await _show_users_page(message=callback.message, user_service=user_service, page=callback_data.page, edit=True)
    await callback.answer()


@router.callback_query(AdminBlockedUsersCallback.filter(), AdminPermissionFilter("users"))
async def blocked_users_page_handler(callback: CallbackQuery, callback_data: AdminBlockedUsersCallback, user_service: UserService) -> None:
    await _show_blocked_users_page(message=callback.message, user_service=user_service, page=callback_data.page, edit=True)
    await callback.answer()


@router.callback_query(AdminUserCallback.filter(), AdminPermissionFilter("users"))
async def user_details_handler(callback: CallbackQuery, callback_data: AdminUserCallback, user_service: UserService) -> None:
    try:
        user = await user_service.get_user(callback_data.telegram_id)
    except UserNotFoundError:
        await callback.answer("کاربر پیدا نشد.", show_alert=True)
        return
    await callback.message.edit_text(
        _user_details_text(user),
        reply_markup=user_actions_keyboard(user, source=callback_data.source, page=callback_data.page),
    )
    await callback.answer()


@router.callback_query(
    AdminUserActionCallback.filter(F.action.in_({"add_coin", "remove_coin"})),
    AdminPermissionFilter("users"),
)
async def coin_action_start_handler(callback: CallbackQuery, callback_data: AdminUserActionCallback, state: FSMContext) -> None:
    await state.set_state(AdminUserStates.waiting_for_coin_amount)
    await state.update_data(
        coin_action=callback_data.action,
        telegram_id=callback_data.telegram_id,
        source=callback_data.source,
        page=callback_data.page,
    )
    action_text = "افزایش" if callback_data.action == "add_coin" else "کاهش"
    await callback.message.answer(
        f"➖➕ مقدار {action_text} سکه را به صورت عدد ارسال کنید:",
        reply_markup=admin_cancel_keyboard,
    )
    await callback.answer()


@router.message(AdminUserStates.waiting_for_coin_amount, AdminPermissionFilter("users"))
async def coin_amount_handler(
    message: Message,
    state: FSMContext,
    user_service: UserService,
    notification_service: NotificationService,
) -> None:
    text = (message.text or "").strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer(
            "❌ مقدار باید یک عدد صحیح بزرگ‌تر از صفر باشد. دوباره ارسال کنید:",
            reply_markup=admin_cancel_keyboard,
        )
        return
    data = await state.get_data()
    amount = int(text)
    telegram_id = data["telegram_id"]
    source = data.get("source", "users")
    page = data.get("page", 0)
    if data["coin_action"] == "add_coin":
        user = await user_service.add_coins(telegram_id, amount)
        await notification_service.coins_added(telegram_id, amount, user.coins)
        notice = f"✅ {amount} سکه اضافه شد."
    else:
        user = await user_service.remove_coins(telegram_id, amount)
        await notification_service.coins_removed(telegram_id, amount, user.coins)
        notice = f"✅ {amount} سکه کم شد."
    await state.clear()
    await message.answer(
        f"{notice}\n\n{_user_details_text(user)}",
        reply_markup=user_actions_keyboard(user, source=source, page=page),
    )


@router.callback_query(AdminUserActionCallback.filter(), AdminPermissionFilter("users"))
async def user_action_handler(
    callback: CallbackQuery,
    callback_data: AdminUserActionCallback,
    user_service: UserService,
    notification_service: NotificationService,
) -> None:
    action = callback_data.action
    telegram_id = callback_data.telegram_id
    if action == "add_warning":
        user = await user_service.add_warning(telegram_id)
        notice = "یک اخطار اضافه شد."
        if user.status is UserStatus.BLOCKED:
            await notification_service.user_auto_blocked(telegram_id)
        else:
            await notification_service.warning_added(telegram_id, user.warnings)
    elif action == "block":
        user = await user_service.block_user(telegram_id)
        notice = "کاربر مسدود شد."
        await notification_service.user_blocked(telegram_id)
    elif action == "unblock":
        user = await user_service.unblock_user(telegram_id)
        await notification_service.user_unblocked(telegram_id)
        notice = "کاربر رفع مسدودیت شد و اخطارها صفر شدند."
        if callback_data.source == "blocked":
            await _show_blocked_users_page(message=callback.message, user_service=user_service, page=callback_data.page, edit=True)
            await callback.answer(notice)
            return
    else:
        await callback.answer("عملیات نامعتبر است.", show_alert=True)
        return
    await callback.message.edit_text(
        _user_details_text(user),
        reply_markup=user_actions_keyboard(user, source=callback_data.source, page=callback_data.page),
    )
    await callback.answer(notice)


@router.callback_query(F.data == "noop")
async def noop_handler(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data == "admin_blocked_users", AdminPermissionFilter("users"))
async def blocked_users_start_handler(callback: CallbackQuery, user_service: UserService) -> None:
    await _show_blocked_users_page(message=callback.message, user_service=user_service, page=0, edit=True)
    await callback.answer()


async def _show_stats_dashboard(*, message: Message, edit: bool) -> None:
    text = "📊 آمار و وضعیت\n\nیکی از گزینه‌ها را انتخاب کنید:"
    keyboard = stats_dashboard_keyboard()
    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


async def _show_user_statistics(*, message: Message, user_service: UserService) -> None:
    stats = await user_service.get_user_statistics()
    text = (
        "👥 آمار کاربران\n\n"
        f"👤 کل کاربران: {stats['total']:,}\n\n"
        f"✅ ثبت‌نام‌شده: {stats['registered']:,}\n"
        f"⏳ ثبت‌نام‌نشده: {stats['unregistered']:,}\n"
        f"🚫 مسدود: {stats['blocked']:,}\n"
        f"🟢 غیرمسدود: {stats['active']:,}\n\n"
        "📅 فعالیت کاربران\n\n"
        f"🟢 فعال امروز: {stats['active_today']:,}\n"
        f"🟡 فعال ۷ روز اخیر: {stats['active_7d']:,}\n"
        f"⚫ غیرفعال بیش از ۳۰ روز: {stats['inactive_30d']:,}"
    )
    await message.edit_text(text, reply_markup=user_stats_keyboard())


async def _show_support_statistics(*, message: Message, support_service: SupportService) -> None:
    stats = await support_service.get_support_statistics()
    text = (
        "🆘 آمار پشتیبانی\n\n"
        f"🎫 کل تیکت‌ها: {stats['total']:,}\n\n"
        f"🟢 باز: {stats['open']:,}\n"
        f"🔴 بسته: {stats['closed']:,}\n\n"
        "📅 فعالیت تیکت‌ها\n\n"
        f"📝 امروز: {stats['today']:,}\n"
        f"📝 ۷ روز اخیر: {stats['last_7_days']:,}\n"
        f"📝 ۳۰ روز اخیر: {stats['last_30_days']:,}"
    )
    await message.edit_text(text, reply_markup=support_stats_keyboard())


async def _show_broadcast_statistics(*, message: Message, broadcast_service: BroadcastService) -> None:
    stats = await broadcast_service.get_broadcast_statistics()
    if stats["latest_total_recipients"] is None:
        text = "📢 آمار همگانی\n\nهنوز هیچ پیام همگانی ارسال نشده است."
    else:
        from core.timezone import TEHRAN_TZ
        latest_dt = stats["latest_created_at"]
        if latest_dt is not None:
            if latest_dt.tzinfo is None:
                latest_dt = latest_dt.replace(tzinfo=TEHRAN_TZ)
            latest_str = latest_dt.strftime("%Y/%m/%d - %H:%M")
        else:
            latest_str = "—"
        duration = stats["latest_duration_seconds"]
        minutes, seconds = divmod(duration, 60)
        duration_str = f"{minutes} دقیقه و {seconds} ثانیه" if minutes else f"{seconds} ثانیه"
        success_rate = stats["latest_success_rate"]
        text = (
            "📢 آمار همگانی\n\n"
            f"📨 کل ارسال‌ها: {stats['total_broadcasts']:,}\n\n"
            "📅 فعالیت ارسال‌ها\n\n"
            f"📝 امروز: {stats['today']:,}\n"
            f"📝 ۷ روز اخیر: {stats['last_7_days']:,}\n"
            f"📝 ۳۰ روز اخیر: {stats['last_30_days']:,}\n\n"
            "📊 آخرین ارسال\n\n"
            f"👥 تعداد دریافت‌کنندگان: {stats['latest_total_recipients']:,}\n"
            f"✅ موفق: {stats['latest_success']:,}\n"
            f"❌ ناموفق: {stats['latest_failed']:,}\n"
            f"📈 نرخ موفقیت: {success_rate:.1f}%\n\n"
            f"📅 زمان ارسال:\n{latest_str}\n"
            f"⏱ مدت زمان: {duration_str}"
        )
    await message.edit_text(text, reply_markup=broadcast_stats_keyboard())


async def _show_antispam_statistics(*, message: Message, antispam_service: AntiSpamService) -> None:
    stats = await antispam_service.get_antispam_statistics()
    text = (
        "🛡️ آمار ضداسپم\n\n"
        f"⚠️ کل اخطارها: {stats['total_warnings']:,}\n"
        f"🚫 کل مسدودشدگان: {stats['total_blocks']:,}\n\n"
        "📅 فعالیت ضداسپم\n\n"
        f"📝 امروز: {stats['today']:,}\n"
        f"📝 ۷ روز اخیر: {stats['last_7_days']:,}\n"
        f"📝 ۳۰ روز اخیر: {stats['last_30_days']:,}"
    )
    await message.edit_text(text, reply_markup=antispam_stats_keyboard())


async def _show_placeholder_statistics(*, message: Message, section: str) -> None:
    await message.edit_text("این بخش به‌زودی اضافه می‌شود.", reply_markup=placeholder_stats_keyboard(section))


async def _show_user_management(*, message: Message, edit: bool = False) -> None:
    text = "👥 مدیریت کاربران\n\nیکی از گزینه‌ها را انتخاب کنید:"
    keyboard = user_management_keyboard()
    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


async def _show_users_page(*, message: Message, user_service: UserService, page: int, edit: bool = False) -> None:
    users, total, page = await user_service.get_users_page(page=page, page_size=_PAGE_SIZE)
    total_pages = max(ceil(total / _PAGE_SIZE), 1)
    keyboard = users_keyboard(users=users, page=page, total_pages=total_pages)
    if total == 0:
        text = "👤 کاربران\n\nهنوز کاربری ثبت‌نام نکرده است."
    else:
        text = "👤 کاربران\n\n" f"تعداد کل کاربران: {total}\n" "برای مشاهده اطلاعات هر کاربر، روی نام او بزنید."
    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


async def _show_blocked_users_page(*, message: Message, user_service: UserService, page: int, edit: bool = False) -> None:
    users, total, page = await user_service.get_blocked_users_page(page=page, page_size=_PAGE_SIZE)
    total_pages = max(ceil(total / _PAGE_SIZE), 1)
    keyboard = blocked_users_keyboard(users=users, page=page, total_pages=total_pages)
    if total == 0:
        text = "🚫 کاربران مسدود\n\nهیچ کاربر مسدودی وجود ندارد."
    else:
        text = "🚫 کاربران مسدود\n\n" f"تعداد کل کاربران مسدود: {total}\n" "برای مشاهده اطلاعات هر کاربر، روی نام او بزنید."
    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


def _user_details_text(user: User) -> str:
    return (
        "👤 اطلاعات کاربر\n\n"
        f"نام: {user.name}\n"
        f"سن: {user.age}\n"
        f"شناسه: {user.telegram_id}\n"
        f"سکه: {user.coins}\n"
        f"اخطار: {user.warnings}\n"
        f"وضعیت: {user.status.value}"
    )
