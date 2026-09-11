from datetime import datetime

import jdatetime

from core.timezone import TEHRAN_TZ


def format_jalali_date(value: datetime) -> str:
    """Render a datetime as a Jalali (Persian calendar) date, e.g. ``1405/06/12``.

    Naive datetimes are assumed to already be Tehran local time (that is how
    MySQL DATETIME columns round-trip in this project); aware ones are
    converted first so the calendar day is always the Tehran day.
    """
    if value.tzinfo is not None:
        value = value.astimezone(TEHRAN_TZ)
    return jdatetime.date.fromgregorian(date=value.date()).strftime("%Y/%m/%d")
