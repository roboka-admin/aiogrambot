from dataclasses import dataclass, field
from datetime import datetime

from core.timezone import tehran_now


@dataclass(slots=True)
class ForceSubscriptionMembershipEvent:
    """A successful membership verification for one configured target."""

    id: int | None
    user_telegram_id: int
    target_chat_id: int
    created_at: datetime = field(default_factory=tehran_now)
