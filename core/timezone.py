from datetime import datetime
from zoneinfo import ZoneInfo

TEHRAN_TZ = ZoneInfo("Asia/Tehran")


def tehran_now() -> datetime:
    return datetime.now(TEHRAN_TZ)


def ensure_tehran(value: datetime) -> datetime:
    """Return an aware Tehran datetime.

    MySQL DATETIME columns round-trip as *naive* values that this project
    stores as Tehran local time; comparing them with ``tehran_now()`` raises
    ``TypeError``. Naive input is tagged as Tehran, aware input is converted.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=TEHRAN_TZ)
    return value.astimezone(TEHRAN_TZ)
