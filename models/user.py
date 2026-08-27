from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from core.timezone import tehran_now


class UserStatus(str, Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"


class RegistrationStatus(str, Enum):
    UNREGISTERED = "unregistered"
    REGISTERED = "registered"


@dataclass(slots=True)
class User:
    """Domain model for every Telegram user known to the bot."""

    telegram_id: int
    telegram_name: str
    username: str | None = None
    name: str | None = None
    age: int | None = None
    coins: int = 0
    warnings: int = 0
    status: UserStatus = UserStatus.ACTIVE
    registration_status: RegistrationStatus = RegistrationStatus.UNREGISTERED
    first_seen_at: datetime = field(default_factory=tehran_now)
    last_seen_at: datetime = field(default_factory=tehran_now)
