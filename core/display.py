"""Presentation helpers shared by handlers."""

from models.user import UserStatus

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize_digits(text: str) -> str:
    """Convert Persian/Arabic-Indic digits to ASCII so numeric input validates."""
    return text.translate(_PERSIAN_DIGITS)


def user_status_label(status: UserStatus) -> str:
    return "✅ فعال" if status is UserStatus.ACTIVE else "🚫 مسدود"


def user_display_name(*, name: str | None, telegram_id: int) -> str:
    """Prefer the stored display name; fall back to the numeric id."""
    return name if name else f"ID: {telegram_id}"
