from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.timezone import tehran_now
from models.base import Base


class ForceSubscriptionTargetRecord(Base):
    __tablename__ = "force_subscription_targets"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invite_link: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=tehran_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=tehran_now, onupdate=tehran_now
    )


class ForceSubscriptionMembershipEventRecord(Base):
    __tablename__ = "force_subscription_membership_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    target_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=tehran_now
    )
