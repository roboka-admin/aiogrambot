from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.user import UserStatus


class UserRecord(Base):
    """SQLAlchemy persistence model for a Telegram user."""

    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    age: Mapped[int]
    coins: Mapped[int] = mapped_column(default=0)
    warnings: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(
        String(20),
        default=UserStatus.ACTIVE.value,
    )
