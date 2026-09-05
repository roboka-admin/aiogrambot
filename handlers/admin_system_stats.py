from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from callbacks.admin import AdminStatsCallback, AdminStatsRefreshCallback
from filters.admin import AdminFilter
from keyboards.admin_stats import system_stats_keyboard
from services.system import SystemService

router = Router()
router.callback_query.filter(AdminFilter())


@router.callback_query(AdminStatsCallback.filter(F.section == "system"))
async def system_stats_handler(
    callback: CallbackQuery,
    system_service: SystemService,
) -> None:
    await _show_system_statistics(
        message=callback.message,
        system_service=system_service,
    )
    await callback.answer()


@router.callback_query(
    AdminStatsRefreshCallback.filter(F.section == "system")
)
async def system_stats_refresh_handler(
    callback: CallbackQuery,
    system_service: SystemService,
) -> None:
    await _show_system_statistics(
        message=callback.message,
        system_service=system_service,
    )
    await callback.answer("بروزرسانی شد.")


async def _edit_message_if_changed(*, message, text: str, reply_markup) -> None:
    if message is None:
        return

    if message.text == text and message.reply_markup == reply_markup:
        return

    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


async def _show_system_statistics(
    *,
    message,
    system_service: SystemService,
) -> None:
    stats = await system_service.get_system_statistics()

    bot_uptime = _format_duration(stats.uptime_seconds)
    server_uptime = _format_duration(stats.server_uptime_seconds)
    started_str = stats.bot_started_at.strftime("%Y/%m/%d - %H:%M")
    current_str = stats.current_time.strftime("%Y/%m/%d - %H:%M:%S")

    cpu = f"{stats.cpu_percent:.1f}%" if stats.cpu_percent is not None else "—"
    memory = _format_memory(stats.memory_used_mb, stats.memory_total_mb, stats.memory_percent)
    disk = _format_disk(stats.disk_used_gb, stats.disk_total_gb, stats.disk_percent)
    database_status = "🟢 سالم" if stats.database_healthy else "🔴 خطا در اتصال"
    row_count = f"{stats.db_row_count:,}" if stats.db_row_count is not None else "—"

    text = (
        "🖥️ وضعیت سیستم\n\n"
        "🤖 ربات\n\n"
        f"⏰ شروع به کار: {started_str}\n"
        f"⏱ زمان فعالیت: {bot_uptime}\n"
        f"📊 کل آپدیت‌ها: {stats.total_updates:,}\n"
        f"❌ کل خطاها: {stats.total_errors:,}\n"
        f"🕐 زمان تهران: {current_str}\n\n"
        "🖥️ منابع سرور\n\n"
        f"⚙️ CPU: {cpu}\n"
        f"🧠 RAM: {memory}\n"
        f"💽 Disk: {disk}\n"
        f"⏱ Uptime سرور: {server_uptime}\n\n"
        "🗃 پایگاه داده\n\n"
        f"🔌 اتصال: {database_status}\n"
        f"📋 تعداد جدول‌ها: {stats.db_table_count:,}\n"
        f"📝 تعداد رکوردها: {row_count}"
    )

    await _edit_message_if_changed(
        message=message,
        text=text,
        reply_markup=system_stats_keyboard(),
    )


def _format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "—"

    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days} روز")
    if hours or days:
        parts.append(f"{hours} ساعت")
    if minutes or hours or days:
        parts.append(f"{minutes} دقیقه")
    parts.append(f"{seconds} ثانیه")
    return " و ".join(parts)


def _format_memory(
    used_mb: int | None,
    total_mb: int | None,
    percent: float | None,
) -> str:
    if used_mb is None or total_mb is None or percent is None:
        return "—"
    return f"{percent:.1f}% ({used_mb / 1024:.1f} / {total_mb / 1024:.1f} GB)"


def _format_disk(
    used_gb: float | None,
    total_gb: float | None,
    percent: float | None,
) -> str:
    if used_gb is None or total_gb is None or percent is None:
        return "—"
    return f"{percent:.1f}% ({used_gb:.2f} / {total_gb:.2f} GB)"
