from datetime import datetime
from zoneinfo import ZoneInfo

from core.jalali import format_jalali_date
from core.timezone import TEHRAN_TZ


def test_format_jalali_date_naive_is_treated_as_tehran() -> None:
    # 2026-03-21 is Nowruz: 1405/01/01.
    assert format_jalali_date(datetime(2026, 3, 21, 12, 0)) == "1405/01/01"


def test_format_jalali_date_converts_aware_datetimes_to_tehran_day() -> None:
    # 23:30 UTC on 2026-03-20 is already 03:00 on 2026-03-21 in Tehran.
    utc_value = datetime(2026, 3, 20, 23, 30, tzinfo=ZoneInfo("UTC"))
    assert format_jalali_date(utc_value) == "1405/01/01"
    assert format_jalali_date(utc_value.astimezone(TEHRAN_TZ)) == "1405/01/01"
