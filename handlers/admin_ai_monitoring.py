from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from callbacks.admin import AdminAIMonitoringCallback, AdminAIProviderCallback
from core.jalali import format_jalali_date
from core.telegram import edit_message_if_changed
from core.timezone import ensure_tehran
from filters.admin import AdminPermissionFilter
from keyboards.admin_ai_monitoring import (
    DIGEST_INTERVAL_CHOICES,
    ai_analysis_result_keyboard,
    ai_digest_interval_keyboard,
    ai_monitoring_home_keyboard,
    ai_provider_detail_keyboard,
    ai_provider_model_prompt_keyboard,
    ai_providers_keyboard,
    ai_reports_keyboard,
)
from models.ai import AIReport
from models.bot_settings import BotSettings
from services.ai_monitoring import (
    AIMonitoringService,
    ConnectionTestResult,
    ProviderView,
    TokenUsage,
)
from services.bot_settings import BotSettingsService
from services.monitoring import MonitoringService
from services.monitoring.rules import Anomaly
from states.admin import AdminAIMonitoringStates

router = Router()
router.message.filter(AdminPermissionFilter("ai_monitoring"))
router.callback_query.filter(AdminPermissionFilter("ai_monitoring"))

_STATUS_LABEL = {
    "ready": "🟢 آماده",
    "cooldown": "🟠 در انتظار (محدودیت)",
    "failed": "🔴 خطا (نیاز به بررسی)",
    "no_key": "🔑 کلید API تنظیم نشده",
    "disabled": "⚪ غیرفعال",
}
_KIND_LABEL = {"gemini": "Gemini API", "openai_compatible": "OpenAI-compatible"}
_SEVERITY_ICON = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️"}
_REPORT_KIND_LABEL = {"anomaly": "هشدار", "digest": "دوره‌ای", "manual": "دستی", "urgent": "فوری"}


# ------------------------------------------------------------------- home


@router.message(F.text == "🤖 مانیتور هوشمند")
async def ai_monitoring_menu_handler(
    message: Message,
    state: FSMContext,
    bot_settings_service: BotSettingsService,
    ai_monitoring_service: AIMonitoringService,
) -> None:
    await state.clear()
    text, keyboard = await _home_view(bot_settings_service, ai_monitoring_service)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(AdminAIMonitoringCallback.filter(F.action == "home"))
async def ai_monitoring_home_handler(
    callback: CallbackQuery,
    state: FSMContext,
    bot_settings_service: BotSettingsService,
    ai_monitoring_service: AIMonitoringService,
) -> None:
    await state.clear()
    text, keyboard = await _home_view(bot_settings_service, ai_monitoring_service)
    await edit_message_if_changed(message=callback.message, text=text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(AdminAIMonitoringCallback.filter(F.action == "toggle"))
async def ai_monitoring_toggle_handler(
    callback: CallbackQuery,
    bot_settings_service: BotSettingsService,
    ai_monitoring_service: AIMonitoringService,
) -> None:
    settings = await bot_settings_service.toggle_ai_monitoring()
    text, keyboard = await _home_view(bot_settings_service, ai_monitoring_service, settings)
    await edit_message_if_changed(message=callback.message, text=text, reply_markup=keyboard)
    await callback.answer(
        "تحلیل هوشمند فعال شد." if settings.ai_monitoring_enabled else "تحلیل هوشمند خاموش شد."
    )


@router.callback_query(AdminAIMonitoringCallback.filter(F.action == "digest_interval"))
async def ai_digest_interval_handler(
    callback: CallbackQuery,
    callback_data: AdminAIMonitoringCallback,
    bot_settings_service: BotSettingsService,
) -> None:
    if callback_data.value in DIGEST_INTERVAL_CHOICES:
        settings = await bot_settings_service.set_ai_digest_interval_hours(callback_data.value)
        note = "ذخیره شد ✅"
    else:
        settings = await bot_settings_service.get_settings()
        note = ""
    await edit_message_if_changed(
        message=callback.message,
        text=(
            "⏱ بازه‌ی گزارش دوره‌ای\n\n"
            "هر چند ساعت یک‌بار، حتی بدون هشدار، یک خلاصه‌ی هوشمند از وضعیت ربات "
            "برای ادمین‌ها ارسال شود؟\n"
            f"مقدار فعلی: هر {settings.ai_digest_interval_hours} ساعت"
        ),
        reply_markup=ai_digest_interval_keyboard(settings.ai_digest_interval_hours),
    )
    await callback.answer(note)


@router.callback_query(AdminAIMonitoringCallback.filter(F.action == "analyse"))
async def ai_analyse_now_handler(
    callback: CallbackQuery,
    monitoring_service: MonitoringService,
) -> None:
    # Model calls take seconds; acknowledge first so the button stops spinning.
    await callback.answer("در حال تحلیل… چند ثانیه صبر کنید.")
    await edit_message_if_changed(
        message=callback.message,
        text="⏳ در حال جمع‌آوری وضعیت و پرسش از مدل…",
        reply_markup=None,
    )
    snapshot, anomalies, analysis = await monitoring_service.analyse_now()

    lines = ["🔎 تحلیل لحظه‌ای", ""]
    if anomalies:
        lines.append("قواعد آستانه‌ای:")
        lines.extend(_anomaly_line(anomaly) for anomaly in anomalies)
    else:
        lines.append("✅ قواعد آستانه‌ای موردی گزارش نکردند.")
    lines.append("")
    if analysis is not None:
        report = analysis.report
        lines.append(f"🤖 تحلیل هوشمند ({report.provider_key}):")
        lines.append(report.summary)
        lines.append(f"🔢 توکن: {report.tokens_in + report.tokens_out:,}")
    else:
        lines.append("🤖 تحلیل هوشمند در دسترس نبود (خاموش است یا هیچ مدلی پاسخ نداد).")
    lines.append("")
    resources = snapshot.resources
    memory = f"{resources.memory_percent:.0f}%" if resources.memory_percent is not None else "—"
    disk = f"{resources.disk_percent:.0f}%" if resources.disk_percent is not None else "—"
    latency = (
        f"{snapshot.database.latency_ms:.0f}ms" if snapshot.database.latency_ms is not None else "—"
    )
    lines.append(f"📊 RAM {memory} | Disk {disk} | DB {latency}")
    await edit_message_if_changed(
        message=callback.message,
        text="\n".join(lines),
        reply_markup=ai_analysis_result_keyboard(),
    )


# --------------------------------------------------------------- providers


@router.callback_query(AdminAIMonitoringCallback.filter(F.action == "providers"))
async def ai_providers_handler(
    callback: CallbackQuery,
    state: FSMContext,
    ai_monitoring_service: AIMonitoringService,
) -> None:
    await state.clear()
    providers = await ai_monitoring_service.list_providers()
    await edit_message_if_changed(
        message=callback.message,
        text=_providers_text(providers),
        reply_markup=ai_providers_keyboard(providers),
    )
    await callback.answer()


@router.callback_query(AdminAIProviderCallback.filter(F.action == "open"))
async def ai_provider_open_handler(
    callback: CallbackQuery,
    callback_data: AdminAIProviderCallback,
    state: FSMContext,
    ai_monitoring_service: AIMonitoringService,
) -> None:
    await state.clear()  # also serves as cancel for the model prompt
    await _show_provider(callback, callback_data.key, ai_monitoring_service)
    await callback.answer()


@router.callback_query(AdminAIProviderCallback.filter(F.action == "toggle"))
async def ai_provider_toggle_handler(
    callback: CallbackQuery,
    callback_data: AdminAIProviderCallback,
    ai_monitoring_service: AIMonitoringService,
) -> None:
    view = await ai_monitoring_service.toggle_provider(callback_data.key)
    await _show_provider(callback, callback_data.key, ai_monitoring_service)
    await callback.answer("فعال شد." if view.config.enabled else "غیرفعال شد.")


@router.callback_query(AdminAIProviderCallback.filter(F.action == "primary"))
async def ai_provider_primary_handler(
    callback: CallbackQuery,
    callback_data: AdminAIProviderCallback,
    ai_monitoring_service: AIMonitoringService,
) -> None:
    await ai_monitoring_service.make_primary(callback_data.key)
    await _show_provider(callback, callback_data.key, ai_monitoring_service)
    await callback.answer("به‌عنوان مدل اصلی انتخاب شد ⭐")


@router.callback_query(AdminAIProviderCallback.filter(F.action == "reset"))
async def ai_provider_reset_handler(
    callback: CallbackQuery,
    callback_data: AdminAIProviderCallback,
    ai_monitoring_service: AIMonitoringService,
) -> None:
    await ai_monitoring_service.reset_provider(callback_data.key)
    await _show_provider(callback, callback_data.key, ai_monitoring_service)
    await callback.answer("وضعیت ریست شد ♻️")


@router.callback_query(AdminAIProviderCallback.filter(F.action == "test"))
async def ai_provider_test_handler(
    callback: CallbackQuery,
    callback_data: AdminAIProviderCallback,
    ai_monitoring_service: AIMonitoringService,
) -> None:
    await callback.answer("در حال تست اتصال…")
    result = await ai_monitoring_service.test_provider(callback_data.key)
    await _show_provider(callback, callback_data.key, ai_monitoring_service, banner=_test_banner(result))


@router.callback_query(AdminAIProviderCallback.filter(F.action == "model"))
async def ai_provider_model_prompt_handler(
    callback: CallbackQuery,
    callback_data: AdminAIProviderCallback,
    state: FSMContext,
    ai_monitoring_service: AIMonitoringService,
) -> None:
    view = await ai_monitoring_service.get_provider(callback_data.key)
    if view is None:
        await callback.answer("مدل پیدا نشد.", show_alert=True)
        return
    await state.set_state(AdminAIMonitoringStates.waiting_for_model_name)
    await state.update_data(provider_key=callback_data.key)
    await edit_message_if_changed(
        message=callback.message,
        text=(
            f"✏️ تغییر مدل {view.config.display_name}\n\n"
            f"مدل فعلی: <code>{view.config.model}</code>\n\n"
            "نام دقیق مدل جدید را بفرستید (مثل <code>gemini-3.5-flash-lite</code> یا "
            "<code>mistral-small-latest</code>). بلافاصله بعد از ذخیره، اتصال تست می‌شود."
        ),
        reply_markup=ai_provider_model_prompt_keyboard(callback_data.key),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminAIMonitoringStates.waiting_for_model_name)
async def ai_provider_model_input_handler(
    message: Message,
    state: FSMContext,
    ai_monitoring_service: AIMonitoringService,
) -> None:
    data = await state.get_data()
    key = data.get("provider_key")
    if not isinstance(key, str):
        await state.clear()
        await message.answer("❌ زمینه‌ی ویرایش از دست رفت؛ دوباره از پنل شروع کنید.")
        return
    try:
        view, result = await ai_monitoring_service.set_model(key, message.text or "")
    except ValueError:
        await message.answer(
            "❌ نام مدل معتبر نیست. یک شناسه‌ی بدون فاصله بفرستید.",
            reply_markup=ai_provider_model_prompt_keyboard(key),
        )
        return
    await state.clear()
    providers = await ai_monitoring_service.list_providers()
    is_primary = bool(providers) and providers[0].config.key == key
    await message.answer(
        _provider_text(view, "✅ مدل ذخیره شد. " + _test_banner(result)),
        reply_markup=ai_provider_detail_keyboard(view, is_primary=is_primary),
    )


# ----------------------------------------------------------------- reports


@router.callback_query(AdminAIMonitoringCallback.filter(F.action == "reports"))
async def ai_reports_handler(
    callback: CallbackQuery,
    callback_data: AdminAIMonitoringCallback,
    ai_monitoring_service: AIMonitoringService,
) -> None:
    page = await ai_monitoring_service.get_reports_page(callback_data.page)
    if not page.reports:
        text = "📜 گزارش‌های اخیر\n\nهنوز گزارشی ثبت نشده است."
    else:
        blocks = [_report_text(report) for report in page.reports]
        text = f"📜 گزارش‌های اخیر ({page.total:,})\n\n" + "\n\n".join(blocks)
    await edit_message_if_changed(
        message=callback.message,
        text=text,
        reply_markup=ai_reports_keyboard(page=page.page, total_pages=page.total_pages),
    )
    await callback.answer()


# ----------------------------------------------------------------- helpers


async def _home_view(
    bot_settings_service: BotSettingsService,
    ai_monitoring_service: AIMonitoringService,
    settings: BotSettings | None = None,
) -> tuple[str, InlineKeyboardMarkup]:
    settings = settings or await bot_settings_service.get_settings()
    providers = await ai_monitoring_service.list_providers()
    usage = await ai_monitoring_service.get_token_usage()
    latest = await ai_monitoring_service.get_latest_report()
    return _home_text(settings, providers, usage, latest), ai_monitoring_home_keyboard(settings)


def _home_text(
    settings: BotSettings,
    providers: list[ProviderView],
    usage: TokenUsage,
    latest: AIReport | None,
) -> str:
    active = next((view for view in providers if view.effective_status == "ready"), None)
    active_label = (
        f"{active.config.display_name} ({active.config.model})" if active else "— هیچ مدلی آماده نیست"
    )
    ready_count = sum(view.effective_status == "ready" for view in providers)
    latest_line = (
        f"{_SEVERITY_ICON.get(latest.severity, 'ℹ️')} {_format_when(latest)} — "
        f"{_REPORT_KIND_LABEL.get(latest.kind.value, latest.kind.value)} ({latest.provider_key})"
        if latest
        else "—"
    )
    return (
        "🤖 مانیتور هوشمند\n\n"
        "هشدارهای آستانه‌ای همیشه فعال‌اند؛ این بخش لایه‌ی تحلیل هوش مصنوعی روی آن‌هاست.\n\n"
        f"وضعیت تحلیل: {'🟢 فعال' if settings.ai_monitoring_enabled else '🔴 خاموش'}\n"
        f"مدل فعال: {active_label}\n"
        f"مدل‌های آماده: {ready_count} از {len(providers)}\n"
        f"گزارش دوره‌ای: هر {settings.ai_digest_interval_hours} ساعت\n\n"
        "🔢 مصرف توکن\n"
        f"امروز: {usage.today_in + usage.today_out:,} "
        f"(ورودی {usage.today_in:,} / خروجی {usage.today_out:,})\n"
        f"۷ روز اخیر: {usage.last_7_days_in + usage.last_7_days_out:,}\n\n"
        f"آخرین گزارش: {latest_line}"
    )


def _providers_text(providers: list[ProviderView]) -> str:
    if not providers:
        return "🧠 مدل‌ها\n\nهیچ مدلی ثبت نشده است."
    lines = ["🧠 مدل‌ها", "", "ترتیب = اولویت؛ اولین مدلِ آماده استفاده می‌شود و در صورت خطا به بعدی می‌رود.", ""]
    for index, view in enumerate(providers, start=1):
        lines.append(
            f"{index}. {view.config.display_name} — {_STATUS_LABEL[view.effective_status]}"
        )
    return "\n".join(lines)


def _provider_text(view: ProviderView, banner: str | None = None) -> str:
    config = view.config
    lines = []
    if banner:
        lines.extend([banner, ""])
    lines.extend(
        [
            f"🧠 {config.display_name}",
            "",
            f"وضعیت: {_STATUS_LABEL[view.effective_status]}",
            f"نوع API: {_KIND_LABEL.get(config.kind.value, config.kind.value)}",
            f"مدل: {config.model}",
            f"اولویت: {config.priority}",
            f"کلید API: متغیر {config.api_key_env} "
            f"({'تنظیم شده ✅' if view.has_api_key else 'تنظیم نشده ❌'})",
            "",
            "🔢 مصرف توکن",
            f"امروز: {view.tokens_today:,}"
            + (f" از بودجه {config.daily_token_budget:,}" if config.daily_token_budget else ""),
            f"کل: {config.tokens_total:,} (ورودی {config.tokens_in_total:,} / خروجی {config.tokens_out_total:,})",
        ]
    )
    if config.last_used_at is not None:
        lines.append(f"آخرین استفاده: {_format_datetime(config.last_used_at)}")
    if config.cooldown_until is not None and view.effective_status == "cooldown":
        lines.append(f"پایان انتظار: {_format_datetime(config.cooldown_until)}")
    if config.last_error:
        lines.extend(["", f"⚠️ آخرین خطا: {config.last_error[:200]}"])
    return "\n".join(lines)


async def _show_provider(
    callback: CallbackQuery,
    key: str,
    ai_monitoring_service: AIMonitoringService,
    *,
    banner: str | None = None,
) -> None:
    providers = await ai_monitoring_service.list_providers()
    view = next((view for view in providers if view.config.key == key), None)
    if view is None:
        await callback.answer("مدل پیدا نشد.", show_alert=True)
        return
    is_primary = providers[0].config.key == key
    await edit_message_if_changed(
        message=callback.message,
        text=_provider_text(view, banner),
        reply_markup=ai_provider_detail_keyboard(view, is_primary=is_primary),
    )


def _test_banner(result: ConnectionTestResult) -> str:
    if result.ok:
        return f"✅ تست موفق — پاسخ: «{result.detail}» ({result.tokens} توکن)"
    return f"❌ تست ناموفق — {result.detail}"


def _report_text(report: AIReport) -> str:
    icon = _SEVERITY_ICON.get(report.severity, "ℹ️")
    kind = _REPORT_KIND_LABEL.get(report.kind.value, report.kind.value)
    header = f"{icon} {_format_when(report)} · {kind} · {report.provider_key} · {report.tokens_in + report.tokens_out} توکن"
    summary = report.summary if len(report.summary) <= 400 else report.summary[:399] + "…"
    return f"{header}\n{summary}"


def _anomaly_line(anomaly: Anomaly) -> str:
    icon = "🚨" if anomaly.severity.value == "critical" else "⚠️"
    return f"{icon} {anomaly.title}" + (f" — {anomaly.detail}" if anomaly.detail else "")


def _format_when(report: AIReport) -> str:
    return _format_datetime(report.created_at)


def _format_datetime(value) -> str:
    local = ensure_tehran(value)
    return f"{format_jalali_date(local)} {local.strftime('%H:%M')}"
