from datetime import datetime

from sqlalchemy import DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class BroadcastRecordRecord(Base):
    """SQLAlchemy persistence model for a broadcast record."""

    __tablename__ = "broadcast_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    total_recipients: Mapped[int] = mapped_column(Integer, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
