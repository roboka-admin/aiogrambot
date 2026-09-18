from datetime import datetime, timedelta, timezone

from core.timezone import TEHRAN_TZ, ensure_tehran, tehran_now


def test_ensure_tehran_tags_naive_values_as_tehran() -> None:
    naive = datetime(2026, 9, 18, 21, 15)
    aware = ensure_tehran(naive)
    assert aware.tzinfo is TEHRAN_TZ
    assert aware.replace(tzinfo=None) == naive
    # the whole point: comparable with tehran_now() without TypeError
    assert aware < tehran_now()


def test_ensure_tehran_converts_aware_values() -> None:
    utc = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
    converted = ensure_tehran(utc)
    assert converted.utcoffset() == timedelta(hours=3, minutes=30)
    assert converted == utc
