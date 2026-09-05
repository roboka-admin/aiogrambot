from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from callbacks.admin import (
    AdminCreateCancelCallback,
    AdminCreateConfirmCallback,
    AdminCreatePermissionCallback,
    AdminManagementCallback,
)
from core.admin_permissions import ADMIN_PERMISSION_REGISTRY
from filters.admin import AdminPermissionFilter
from keyboards.admin_management import (
    admin_detail_keyboard,
    admin_management_keyboard,
    admins_keyboard,
    permission_selection_keyboard,
)
from models.admin import AdminRole
from services.admin import AdminService
from states.admin import AdminManagementStates

router = Router()
router.message.filter(AdminPermissionFilter("admins"))
router.callback_query.filter(AdminPermissionFilter("admins"))


async def _show_management(message: Message, admin_service: AdminService) -> None:
    admins = await admin_service.list_admins()
    await message.answer(
        f"🛡 مدیریت ادمین‌ها\n\nتعداد ادمین‌ها: {len(admins)}",
        reply_markup=admin_management_keyboard(),
    )


@router.message(F.text == "🛡 مدیریت ادمین‌ها")
async def admin_management_handler(
    message: Message, admin_service: AdminService, state: FSMContext
) -> None:
    await state.clear()
    await _show_management(message, admin_service)


@router.callback_query(AdminManagementCallback.filter(F.action == "list"))
async def admin_list_handler(callback: CallbackQuery, admin_service: AdminService) -> None:
    admins = await admin_service.list_admins()
    if not admins:
        text = "👥 هیچ ادمینی ثبت نشده است."
    else:
        text = "👥 فهرست ادمین‌ها\n\nبرای مشاهده جزئیات، ادمین موردنظر را انتخاب کنید."
    await callback.message.edit_text(text, reply_markup=admins_keyboard(admins))
    await callback.answer()


@router.callback_query(AdminManagementCallback.filter(F.action == "view"))
async def admin_view_handler(
    callback: CallbackQuery,
    callback_data: AdminManagementCallback,
    admin_service: AdminService,
) -> None:
    admin = await admin_service.get_admin(callback_data.telegram_id)
    if admin is None:
        await callback.answer("این ادمین دیگر وجود ندارد.", show_alert=True)
        return

    if admin.role is AdminRole.OWNER:
        text = f"👑 ادمین اصلی\n\nشناسه: {admin.telegram_id}\nوضعیت: فعال"
    else:
        permissions = await admin_service.get_permissions(admin.telegram_id)
        titles = {
            permission.key: permission.title for permission in ADMIN_PERMISSION_REGISTRY
        }
        permission_text = "\n".join(
            f"• {titles[key]}" for key in sorted(permissions) if key in titles
        ) or "• بدون دسترسی"
        status = "فعال" if admin.status.value == "active" else "غیرفعال"
        text = (
            f"👤 ادمین: {admin.telegram_id}\n"
            f"وضعیت: {status}\n\n"
            f"دسترسی‌ها:\n{permission_text}"
        )

    await callback.message.edit_text(text, reply_markup=admin_detail_keyboard(admin))
    await callback.answer()


@router.callback_query(AdminManagementCallback.filter(F.action == "create"))
async def admin_create_start_handler(
    callback: CallbackQuery, state: FSMContext
) -> None:
    await state.set_state(AdminManagementStates.waiting_for_admin_id)
    await callback.message.edit_text(
        "➕ افزودن ادمین\n\nشناسه عددی Telegram کاربر را ارسال کنید."
    )
    await callback.answer()


@router.message(AdminManagementStates.waiting_for_admin_id)
async def admin_create_id_handler(
    message: Message, state: FSMContext, admin_service: AdminService
) -> None:
    if not message.text or not message.text.strip().isdigit():
        await message.answer("❌ شناسه باید یک عدد معتبر باشد. دوباره ارسال کنید.")
        return

    telegram_id = int(message.text.strip())
    if telegram_id <= 0:
        await message.answer("❌ شناسه باید بزرگ‌تر از صفر باشد.")
        return

    if await admin_service.get_admin(telegram_id) is not None:
        await message.answer("❌ این کاربر از قبل ادمین است.")
        return

    actor_permissions = await admin_service.get_effective_permissions(message.from_user.id)
    permissions = [
        permission
        for permission in ADMIN_PERMISSION_REGISTRY
        if permission.key in actor_permissions
    ]
    await state.update_data(admin_id=telegram_id, permission_keys=[])
    await state.set_state(AdminManagementStates.waiting_for_permission_selection)
    await message.answer(
        f"👤 ادمین جدید: {telegram_id}\n\nدسترسی‌های موردنظر را انتخاب کنید:",
        reply_markup=permission_selection_keyboard(permissions, []),
    )


@router.callback_query(AdminCreatePermissionCallback.filter())
async def admin_permission_toggle_handler(
    callback: CallbackQuery,
    callback_data: AdminCreatePermissionCallback,
    state: FSMContext,
    admin_service: AdminService,
) -> None:
    data = await state.get_data()
    if await state.get_state() != AdminManagementStates.waiting_for_permission_selection:
        await callback.answer("این عملیات دیگر فعال نیست.", show_alert=True)
        return

    selected = set(data.get("permission_keys", []))
    key = callback_data.permission_key
    actor_permissions = await admin_service.get_effective_permissions(callback.from_user.id)
    if key not in actor_permissions:
        await callback.answer("شما این دسترسی را ندارید.", show_alert=True)
        return

    if key in selected:
        selected.remove(key)
    else:
        selected.add(key)
    await state.update_data(permission_keys=sorted(selected))

    permissions = [
        permission
        for permission in ADMIN_PERMISSION_REGISTRY
        if permission.key in actor_permissions
    ]
    await callback.message.edit_reply_markup(
        reply_markup=permission_selection_keyboard(permissions, selected)
    )
    await callback.answer()


@router.callback_query(AdminCreateConfirmCallback.filter())
async def admin_create_confirm_handler(
    callback: CallbackQuery, state: FSMContext, admin_service: AdminService
) -> None:
    data = await state.get_data()
    if await state.get_state() != AdminManagementStates.waiting_for_permission_selection:
        await callback.answer("این عملیات دیگر فعال نیست.", show_alert=True)
        return

    try:
        admin = await admin_service.create_managed_admin(
            actor_telegram_id=callback.from_user.id,
            telegram_id=int(data["admin_id"]),
            permission_keys=set(data.get("permission_keys", [])),
        )
    except (PermissionError, ValueError) as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    await state.clear()
    await callback.message.edit_text(
        f"✅ ادمین {admin.telegram_id} با موفقیت اضافه شد.",
        reply_markup=admin_management_keyboard(),
    )
    await callback.answer()


@router.callback_query(AdminCreateCancelCallback.filter())
async def admin_create_cancel_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "🛡 مدیریت ادمین‌ها",
        reply_markup=admin_management_keyboard(),
    )
    await callback.answer("لغو شد.")


@router.callback_query(AdminManagementCallback.filter(F.action == "deactivate"))
async def admin_deactivate_handler(
    callback: CallbackQuery,
    callback_data: AdminManagementCallback,
    admin_service: AdminService,
) -> None:
    changed = await admin_service.deactivate_managed_admin(
        actor_telegram_id=callback.from_user.id,
        telegram_id=callback_data.telegram_id,
    )
    await callback.answer("ادمین غیرفعال شد." if changed else "امکان انجام این کار وجود ندارد.", show_alert=not changed)
    if changed:
        admin = await admin_service.get_admin(callback_data.telegram_id)
        if admin:
            await callback.message.edit_reply_markup(reply_markup=admin_detail_keyboard(admin))


@router.callback_query(AdminManagementCallback.filter(F.action == "activate"))
async def admin_activate_handler(
    callback: CallbackQuery,
    callback_data: AdminManagementCallback,
    admin_service: AdminService,
) -> None:
    changed = await admin_service.activate_managed_admin(
        actor_telegram_id=callback.from_user.id,
        telegram_id=callback_data.telegram_id,
    )
    await callback.answer("ادمین فعال شد." if changed else "امکان انجام این کار وجود ندارد.", show_alert=not changed)
    if changed:
        admin = await admin_service.get_admin(callback_data.telegram_id)
        if admin:
            await callback.message.edit_reply_markup(reply_markup=admin_detail_keyboard(admin))


@router.callback_query(AdminManagementCallback.filter(F.action == "delete"))
async def admin_delete_handler(
    callback: CallbackQuery,
    callback_data: AdminManagementCallback,
    admin_service: AdminService,
) -> None:
    removed = await admin_service.remove_managed_admin(
        actor_telegram_id=callback.from_user.id,
        telegram_id=callback_data.telegram_id,
    )
    await callback.answer("ادمین حذف شد." if removed else "امکان انجام این کار وجود ندارد.", show_alert=not removed)
    if removed:
        admins = await admin_service.list_admins()
        await callback.message.edit_text(
            "👥 فهرست ادمین‌ها",
            reply_markup=admins_keyboard(admins),
        )
