from dataclasses import dataclass
from enum import Enum


class UserStatus(str, Enum):
    """
    Represents the current status of a user.
    """

    ACTIVE = "active"
    BLOCKED = "blocked"


@dataclass(slots=True)
class User:
    """
    Domain model representing a Telegram user.
    """

    telegram_id: int
    name: str
    age: int

    coins: int = 0
    warnings: int = 0

    status: UserStatus = UserStatus.ACTIVE