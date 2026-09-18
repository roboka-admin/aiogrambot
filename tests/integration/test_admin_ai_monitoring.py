from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from callbacks.admin import AdminAIMonitoringCallback, AdminAIProviderCallback
from handlers.admin_ai_monitoring import (
    _home_text,
    _provider_text,
    ai_analyse_now_handler,
    ai_digest_interval_handler,
    ai_monitoring_toggle_handler,
    ai_provider_model_input_handler,
    ai_provider_test_handler,
    ai_reports_handler,
)
from keyboards.admin_ai_monitoring import (
    ai_monitoring_home_keyboard,
    ai_provider_detail_keyboard,
    ai_reports_keyboard,
)
from models.ai import AIProviderStatus, AIReport, AIReportKind
from models.bot_settings import BotSettings
from services.ai_monitoring import (
    ConnectionTestResult,
    ProviderView,
    ReportsPage,
    TokenUsage,
)
from services.monitoring.analysis import AIAnalysis
from services.monitoring.rules import Anomaly, Severity
from tests.services.ai.fakes import config
from tests.services.monitoring.test_rules import make_snapshot


def view(key="gemini", **overrides) -> ProviderView:
    has_key = overrides.pop("has_api_key", True)
    tokens_today = overrides.pop("tokens_today", 0)
    return ProviderView(
        config=config(key, 10, api_key_env="G", **overrides),
        has_api_key=has_key,
        tokens_today=tokens_today,
    )


def report(**overrides) -> AIReport:
    base = dict(
        id=1,
        kind=AIReportKind.DIGEST,
        provider_key="gemini",
        severity="info",
        summary="همه‌چیز عادی است.",
        anomaly_keys="",
        tokens_in=300,
        tokens_out=60,
        created_at=datetime(2026, 9, 18, 21, 24),  # naive, as MySQL returns it
    )
    base.update(overrides)
    return AIReport(**base)


def make_callback() -> MagicMock:
    callback = MagicMock()
    callback.message = MagicMock()
    callback.message.text = ""
    callback.message.reply_markup = None
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    return callback


# ------------------------------------------------------------------ texts


def test_home_text_shows_active_provider_tokens_and_latest_report() -> None:
    settings = BotSettings(ai_monitoring_enabled=True, ai_digest_interval_hours=12)
    providers = [
        view("mistral", status=AIProviderStatus.COOLDOWN),
        view("gemini", model="gemini-3.5-flash-lite"),
    ]
    usage = TokenUsage(today_in=300, today_out=60, last_7_days_in=1000, last_7_days_out=200)
    text = _home_text(settings, providers, usage, report())

    assert "🟢 فعال" in text
    assert "Gemini (gemini-3.5-flash-lite)" in text
    assert "مدل‌های آماده: 1 از 2" in text
    assert "هر 12 ساعت" in text
    assert "امروز: 360" in text
    assert "۷ روز اخیر: 1,200" in text
    assert "1405/06/27 21:24" in text


def test_home_text_when_no_provider_is_ready() -> None:
    text = _home_text(BotSettings(), [view(has_api_key=False)], TokenUsage(0, 0, 0, 0), None)
    assert "هیچ مدلی آماده نیست" in text
    assert "آخرین گزارش: —" in text


def test_provider_text_includes_key_state_budget_and_error() -> None:
    text = _provider_text(
        view(
            daily_token_budget=200_000,
            tokens_today=1234,
            tokens_in_total=5000,
            tokens_out_total=700,
            last_error="gemini: 404 model not found",
            has_api_key=False,
        )
    )
    assert "🔑 کلید API تنظیم نشده" in text
    assert "متغیر G (تنظیم نشده ❌)" in text
    assert "امروز: 1,234 از بودجه 200,000" in text
    assert "کل: 5,700" in text
    assert "⚠️ آخرین خطا: gemini: 404 model not found" in text


# -------------------------------------------------------------- keyboards


def test_home_keyboard_reflects_toggle_state() -> None:
    on = ai_monitoring_home_keyboard(BotSettings(ai_monitoring_enabled=True))
    off = ai_monitoring_home_keyboard(BotSettings(ai_monitoring_enabled=False))
    assert on.inline_keyboard[0][0].text.startswith("🟢")
    assert off.inline_keyboard[0][0].text.startswith("🔴")
    assert on.inline_keyboard[0][0].callback_data == AdminAIMonitoringCallback(action="toggle").pack()


def test_provider_detail_keyboard_hides_primary_button_for_primary() -> None:
    primary = ai_provider_detail_keyboard(view(), is_primary=True)
    secondary = ai_provider_detail_keyboard(view(), is_primary=False)
    primary_data = AdminAIProviderCallback(action="primary", key="gemini").pack()
    assert all(b.callback_data != primary_data for row in primary.inline_keyboard for b in row)
    assert any(b.callback_data == primary_data for row in secondary.inline_keyboard for b in row)


def test_reports_keyboard_navigation_edges() -> None:
    first = ai_reports_keyboard(page=0, total_pages=3)
    assert [b.text for b in first.inline_keyboard[0]] == ["1 / 3", "قدیمی‌تر ➡️"]
    last = ai_reports_keyboard(page=2, total_pages=3)
    assert [b.text for b in last.inline_keyboard[0]] == ["⬅️ جدیدتر", "3 / 3"]
    only = ai_reports_keyboard(page=0, total_pages=1)
    assert [b.text for b in only.inline_keyboard[0]] == ["1 / 1"]


# --------------------------------------------------------------- handlers


async def test_toggle_handler_flips_setting_and_redraws_home() -> None:
    callback = make_callback()
    settings_service = MagicMock()
    settings_service.toggle_ai_monitoring = AsyncMock(
        return_value=BotSettings(ai_monitoring_enabled=False)
    )
    ai_service = MagicMock()
    ai_service.list_providers = AsyncMock(return_value=[view()])
    ai_service.get_token_usage = AsyncMock(return_value=TokenUsage(0, 0, 0, 0))
    ai_service.get_latest_report = AsyncMock(return_value=None)

    await ai_monitoring_toggle_handler(callback, settings_service, ai_service)

    settings_service.toggle_ai_monitoring.assert_awaited_once()
    text = callback.message.edit_text.await_args.args[0]
    assert "وضعیت تحلیل: 🔴 خاموش" in text
    callback.answer.assert_awaited_once_with("تحلیل هوشمند خاموش شد.")


async def test_digest_interval_handler_saves_only_known_choices() -> None:
    settings_service = MagicMock()
    settings_service.set_ai_digest_interval_hours = AsyncMock(
        return_value=BotSettings(ai_digest_interval_hours=6)
    )
    settings_service.get_settings = AsyncMock(return_value=BotSettings())

    callback = make_callback()
    await ai_digest_interval_handler(
        callback, AdminAIMonitoringCallback(action="digest_interval", value=6), settings_service
    )
    settings_service.set_ai_digest_interval_hours.assert_awaited_once_with(6)
    callback.answer.assert_awaited_once_with("ذخیره شد ✅")

    callback = make_callback()
    await ai_digest_interval_handler(
        callback, AdminAIMonitoringCallback(action="digest_interval", value=7), settings_service
    )
    settings_service.set_ai_digest_interval_hours.assert_awaited_once()  # not called again
    callback.answer.assert_awaited_once_with("")


async def test_analyse_now_handler_renders_anomalies_and_ai_summary() -> None:
    callback = make_callback()
    anomaly = Anomaly(key="ram", severity=Severity.WARNING, title="RAM بالا", detail="85%")
    analysis = AIAnalysis(report=report(kind=AIReportKind.MANUAL), switched_from=None)
    monitoring = MagicMock()
    monitoring.analyse_now = AsyncMock(return_value=(make_snapshot(), [anomaly], analysis))

    await ai_analyse_now_handler(callback, monitoring)

    final_text = callback.message.edit_text.await_args_list[-1].args[0]
    assert "⚠️ RAM بالا — 85%" in final_text
    assert "🤖 تحلیل هوشمند (gemini):" in final_text
    assert "همه‌چیز عادی است." in final_text
    assert "🔢 توکن: 360" in final_text
    assert "RAM 40%" in final_text
    callback.answer.assert_awaited_once()


async def test_analyse_now_handler_when_ai_unavailable() -> None:
    callback = make_callback()
    monitoring = MagicMock()
    monitoring.analyse_now = AsyncMock(return_value=(make_snapshot(), [], None))

    await ai_analyse_now_handler(callback, monitoring)

    final_text = callback.message.edit_text.await_args_list[-1].args[0]
    assert "✅ قواعد آستانه‌ای موردی گزارش نکردند." in final_text
    assert "در دسترس نبود" in final_text


async def test_provider_test_handler_shows_banner() -> None:
    callback = make_callback()
    ai_service = MagicMock()
    ai_service.test_provider = AsyncMock(
        return_value=ConnectionTestResult(ok=True, provider_key="gemini", detail="OK", tokens=8)
    )
    ai_service.list_providers = AsyncMock(return_value=[view()])

    await ai_provider_test_handler(
        callback, AdminAIProviderCallback(action="test", key="gemini"), ai_service
    )

    text = callback.message.edit_text.await_args.args[0]
    assert text.startswith("✅ تست موفق — پاسخ: «OK» (8 توکن)")


async def test_model_input_handler_rejects_invalid_then_saves() -> None:
    state = MagicMock()
    state.get_data = AsyncMock(return_value={"provider_key": "gemini"})
    state.clear = AsyncMock()
    ai_service = MagicMock()
    ai_service.set_model = AsyncMock(side_effect=ValueError("bad"))
    message = MagicMock()
    message.text = "two words"
    message.answer = AsyncMock()

    await ai_provider_model_input_handler(message, state, ai_service)
    assert "معتبر نیست" in message.answer.await_args.args[0]
    state.clear.assert_not_awaited()

    failed = view(model="gemini-9", status=AIProviderStatus.FAILED, last_error="HTTP 404")
    ai_service.set_model = AsyncMock(
        return_value=(
            failed,
            ConnectionTestResult(ok=False, provider_key="gemini", detail="HTTP 404: not found"),
        )
    )
    ai_service.list_providers = AsyncMock(return_value=[failed])
    message.text = "gemini-9"
    await ai_provider_model_input_handler(message, state, ai_service)

    ai_service.set_model.assert_awaited_once_with("gemini", "gemini-9")
    state.clear.assert_awaited_once()
    text = message.answer.await_args.args[0]
    assert text.startswith("✅ مدل ذخیره شد. ❌ تست ناموفق — HTTP 404: not found")
    assert "وضعیت: 🔴 خطا (نیاز به بررسی)" in text
    assert "مدل: gemini-9" in text


async def test_reports_handler_lists_reports_and_empty_state() -> None:
    ai_service = MagicMock()
    ai_service.get_reports_page = AsyncMock(
        return_value=ReportsPage(reports=[report()], page=0, total_pages=1, total=1)
    )
    callback = make_callback()
    await ai_reports_handler(callback, AdminAIMonitoringCallback(action="reports"), ai_service)
    text = callback.message.edit_text.await_args.args[0]
    assert "📜 گزارش‌های اخیر (1)" in text
    assert "1405/06/27 21:24 · دوره‌ای · gemini · 360 توکن" in text

    ai_service.get_reports_page = AsyncMock(
        return_value=ReportsPage(reports=[], page=0, total_pages=1, total=0)
    )
    callback = make_callback()
    await ai_reports_handler(callback, AdminAIMonitoringCallback(action="reports"), ai_service)
    assert "هنوز گزارشی ثبت نشده است." in callback.message.edit_text.await_args.args[0]
