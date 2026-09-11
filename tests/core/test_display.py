from core.display import normalize_digits, user_display_name, user_status_label
from models.user import UserStatus


def test_normalize_digits_handles_persian_and_arabic_indic() -> None:
    assert normalize_digits("۲۸") == "28"
    assert normalize_digits("٤٢") == "42"
    assert normalize_digits("abc 12") == "abc 12"


def test_user_status_label_is_localized() -> None:
    assert user_status_label(UserStatus.ACTIVE) == "✅ فعال"
    assert user_status_label(UserStatus.BLOCKED) == "🚫 مسدود"


def test_user_display_name_falls_back_to_id() -> None:
    assert user_display_name(name="Ali", telegram_id=1) == "Ali"
    assert user_display_name(name=None, telegram_id=1) == "ID: 1"
    assert user_display_name(name="", telegram_id=1) == "ID: 1"
