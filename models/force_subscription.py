from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from core.timezone import tehran_now


class ForceSubscriptionTargetType(str, Enum):
    CHANNEL = "channel"
    SUPERGROUP = "supergroup"


@dataclass
class ForceSubscriptionTarget:
    chat_id: int
    title: str
    target_type: ForceSubscriptionTargetType
    username: str | None = None
    invite_link: str | None = None
    is_active: bool = True
    created_at: datetime = field(default_factory=tehran_now)
    updated_at: datetime = field(default_factory=tehran_now)
