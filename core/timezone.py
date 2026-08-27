from datetime import datetime
from zoneinfo import ZoneInfo

TEHRAN_TZ = ZoneInfo("Asia/Tehran")


def tehran_now() -> datetime:
    return datetime.now(TEHRAN_TZ)
