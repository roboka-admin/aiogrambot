from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from core.timezone import tehran_now
from models.antispam import AntiSpamEventType
from models.base import Base


class AntiSpamEventRecord(Base):
    """SQLAlchemy persistence model for anti-spam events."""

    __tablename__ = "antispam_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    event_type: Mapped[str] = mapped_column(
        SQLEnum(AntiSpamEventType),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=tehran_now,
        nullable=False,
    )
