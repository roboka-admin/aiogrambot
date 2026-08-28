from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from core.timezone import tehran_now
from models.base import Base
from models.support import SupportStatus


class SupportTicketRecord(Base):
    """SQLAlchemy persistence model for a support ticket."""

    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    message: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(
        String(20),
        default=SupportStatus.OPEN.value,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=tehran_now,
        nullable=False,
    )
