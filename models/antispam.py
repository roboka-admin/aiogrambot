from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from core.timezone import tehran_now


class AntiSpamEventType(str, Enum):
    WARNING = "warning"
    BLOCK = "block"


@dataclass(slots=True)
class AntiSpamEvent:
    """Record of an anti-spam action (warning or block)."""

    id: int | None
    user_telegram_id: int
    event_type: AntiSpamEventType
    created_at: datetime = field(default_factory=tehran_now)
