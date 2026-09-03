from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from core.timezone import tehran_now
from models.base import Base
from models.bot_settings import DEFAULT_MAINTENANCE_MESSAGE, DEFAULT_OFFLINE_MESSAGE


class BotSettingsRecord(Base):
    __tablename__ = "bot_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False, default=1)
    bot_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    maintenance_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    antispam_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    force_subscription_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    offline_message: Mapped[str] = mapped_column(String(1000), default=DEFAULT_OFFLINE_MESSAGE)
    maintenance_message: Mapped[str] = mapped_column(String(1000), default=DEFAULT_MAINTENANCE_MESSAGE)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=tehran_now, onupdate=tehran_now)
