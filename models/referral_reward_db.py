from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from core.timezone import tehran_now
from models.base import Base


class ReferralRewardRecord(Base):
    __tablename__ = "referral_rewards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    triggered_by_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    coins: Mapped[int] = mapped_column(Integer, nullable=False)
    invites_consumed: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=tehran_now
    )
