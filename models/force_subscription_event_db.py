from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from core.timezone import tehran_now
from models.base import Base


class ForceSubscriptionMembershipEventRecord(Base):
    __tablename__ = "force_subscription_membership_events"
    __table_args__ = (
        Index("ix_force_subscription_events_created_at", "created_at"),
        Index("ix_force_subscription_events_target_created", "target_chat_id", "created_at"),
        Index("ix_force_subscription_events_user_created", "user_telegram_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    target_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=tehran_now
    )
