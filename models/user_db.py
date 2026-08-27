from datetime import datetime
from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.user import RegistrationStatus, UserStatus


class UserRecord(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    telegram_name: Mapped[str] = mapped_column(String(100), default="")
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    age: Mapped[int | None] = mapped_column(nullable=True)
    coins: Mapped[int] = mapped_column(default=0)
    warnings: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(20), default=UserStatus.ACTIVE.value)
    registration_status: Mapped[str] = mapped_column(
        String(20), default=RegistrationStatus.UNREGISTERED.value
    )
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
