from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SupportStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


@dataclass(slots=True)
class SupportTicket:
    id: int | None
    user_telegram_id: int
    message: str
    status: SupportStatus = SupportStatus.OPEN
    created_at: datetime | None = None
    closed_at: datetime | None = None  # set when status becomes CLOSED; drives retention


@dataclass(slots=True)
class SupportUserSummary:
    user_telegram_id: int
    ticket_count: int
