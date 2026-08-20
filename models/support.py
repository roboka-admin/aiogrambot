from dataclasses import dataclass
from enum import Enum


class SupportStatus(str, Enum):
    """Represents the current status of a support ticket."""

    OPEN = "open"
    CLOSED = "closed"


@dataclass(slots=True)
class SupportTicket:
    """Domain model representing a user support ticket."""

    id: int | None
    user_telegram_id: int
    message: str
    status: SupportStatus = SupportStatus.OPEN
