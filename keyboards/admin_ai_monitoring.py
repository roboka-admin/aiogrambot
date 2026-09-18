from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from callbacks.admin import AdminAIMonitoringCallback, AdminAIProviderCallback
from models.bot_settings import BotSettings
from services.ai_monitoring import ProviderView

DIGEST_INTERVAL_CHOICES: tuple[int, ...] = (6, 12, 24, 48)

_STATUS_ICON = {
    "ready": "🟢",
    "cooldown": "🟠",
    "failed": "🔴",
    "no_key": "🔑",
    "disabled": "⚪",
}


def ai_monitoring_home_keyboard(settings: BotSettings) -> InlineKeyboardMarkup:
    toggle_label = (
        "🟢 تحلیل هوشمند فعال" if settings.ai_monitoring_enabled else "🔴 تحلیل هوشمند خاموش"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=toggle_label,
                    callback_data=AdminAIMonitoringCallback(action="toggle").pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🧠 مدل‌ها",
                    callback_data=AdminAIMonitoringCallback(action="providers").pack(),
                ),
                InlineKeyboardButton(
                    text="📜 گزارش‌های اخیر",
                    callback_data=AdminAIMonitoringCallback(action="reports").pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"⏱ گزارش دوره‌ای: هر {settings.ai_digest_interval_hours} ساعت",
                    callback_data=AdminAIMonitoringCallback(action="digest_interval").pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="▶️ تحلیل همین حالا",
                    callback_data=AdminAIMonitoringCallback(action="analyse").pack(),
                ),
            ],
        ]
    )


def ai_digest_interval_keyboard(current_hours: int) -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton(
            text=f"{'✅ ' if hours == current_hours else ''}{hours} ساعت",
            callback_data=AdminAIMonitoringCallback(action="digest_interval", value=hours).pack(),
        )
        for hours in DIGEST_INTERVAL_CHOICES
    ]
    return InlineKeyboardMarkup(inline_keyboard=[row, [_home_button()]])


def ai_providers_keyboard(providers: list[ProviderView]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=(
                    f"{_STATUS_ICON[view.effective_status]} {view.config.display_name}"
                    f" · {view.config.model}"
                ),
                callback_data=AdminAIProviderCallback(action="open", key=view.config.key).pack(),
            )
        ]
        for view in providers
    ]
    rows.append([_home_button()])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ai_provider_detail_keyboard(view: ProviderView, *, is_primary: bool) -> InlineKeyboardMarkup:
    key = view.config.key
    toggle_label = "⚪ غیرفعال کردن" if view.config.enabled else "🟢 فعال کردن"
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=toggle_label,
                callback_data=AdminAIProviderCallback(action="toggle", key=key).pack(),
            ),
            InlineKeyboardButton(
                text="🔌 تست اتصال",
                callback_data=AdminAIProviderCallback(action="test", key=key).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="✏️ تغییر مدل",
                callback_data=AdminAIProviderCallback(action="model", key=key).pack(),
            ),
            InlineKeyboardButton(
                text="♻️ ریست وضعیت",
                callback_data=AdminAIProviderCallback(action="reset", key=key).pack(),
            ),
        ],
    ]
    if not is_primary:
        rows.append(
            [
                InlineKeyboardButton(
                    text="⭐ انتخاب به‌عنوان مدل اصلی",
                    callback_data=AdminAIProviderCallback(action="primary", key=key).pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="🔙 مدل‌ها",
                callback_data=AdminAIMonitoringCallback(action="providers").pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ai_provider_model_prompt_keyboard(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ انصراف",
                    callback_data=AdminAIProviderCallback(action="open", key=key).pack(),
                )
            ]
        ]
    )


def ai_reports_keyboard(*, page: int, total_pages: int) -> InlineKeyboardMarkup:
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                text="⬅️ جدیدتر",
                callback_data=AdminAIMonitoringCallback(action="reports", page=page - 1).pack(),
            )
        )
    nav.append(InlineKeyboardButton(text=f"{page + 1} / {total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(
            InlineKeyboardButton(
                text="قدیمی‌تر ➡️",
                callback_data=AdminAIMonitoringCallback(action="reports", page=page + 1).pack(),
            )
        )
    return InlineKeyboardMarkup(inline_keyboard=[nav, [_home_button()]])


def ai_analysis_result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_home_button()]])


def _home_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text="🔙 مانیتور هوشمند",
        callback_data=AdminAIMonitoringCallback(action="home").pack(),
    )
