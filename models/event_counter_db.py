from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from core.timezone import tehran_now
from models.base import Base


class EventCounterRecord(Base):
    """Rows pruned from an event table, folded into a single number per kind."""

    __tablename__ = "event_counters"

    kind: Mapped[str] = mapped_column(String(64), primary_key=True)
    archived_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=tehran_now, onupdate=tehran_now
    )
