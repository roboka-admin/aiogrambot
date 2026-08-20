from dataclasses import dataclass
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


@dataclass(slots=True)
class SupportUserSummary:
    user_telegram_id: int
    ticket_count: int
