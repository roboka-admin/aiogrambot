from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.timezone import tehran_now
from models.base import Base
from models.bot_settings import (
    DEFAULT_AI_DIGEST_INTERVAL_HOURS,
    DEFAULT_AI_MONITORING_ENABLED,
    DEFAULT_MAINTENANCE_MESSAGE,
    DEFAULT_OFFLINE_MESSAGE,
    DEFAULT_REFERRAL_REWARD_COINS,
    DEFAULT_REFERRAL_REWARD_PER_INVITES,
)


class BotSettingsRecord(Base):
    __tablename__ = "bot_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False, default=1)
    bot_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    maintenance_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    antispam_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    force_subscription_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    offline_message: Mapped[str] = mapped_column(String(1000), default=DEFAULT_OFFLINE_MESSAGE)
    maintenance_message: Mapped[str] = mapped_column(String(1000), default=DEFAULT_MAINTENANCE_MESSAGE)
    referral_reward_coins: Mapped[int] = mapped_column(Integer, default=DEFAULT_REFERRAL_REWARD_COINS)
    referral_reward_per_invites: Mapped[int] = mapped_column(Integer, default=DEFAULT_REFERRAL_REWARD_PER_INVITES)
    ai_monitoring_enabled: Mapped[bool] = mapped_column(Boolean, default=DEFAULT_AI_MONITORING_ENABLED)
    ai_digest_interval_hours: Mapped[int] = mapped_column(Integer, default=DEFAULT_AI_DIGEST_INTERVAL_HOURS)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=tehran_now, onupdate=tehran_now)
