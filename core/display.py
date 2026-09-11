"""Presentation helpers shared by admin handlers."""


def user_display_name(*, name: str | None, telegram_id: int) -> str:
    """Prefer the stored display name; fall back to the numeric id."""
    return name if name else f"ID: {telegram_id}"
