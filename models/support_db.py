from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

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
