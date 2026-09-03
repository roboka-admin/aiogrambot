from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.bot_settings import BotSettings
from models.bot_settings_db import BotSettingsRecord
from repositories.interfaces.bot_settings import IBotSettingsRepository


class BotSettingsRepository(IBotSettingsRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self) -> BotSettings | None:
        result = await self._session.execute(
            select(BotSettingsRecord).where(BotSettingsRecord.id == 1)
        )
        record = result.scalar_one_or_none()
        return None if record is None else self._to_domain(record)

    async def create(self, settings: BotSettings) -> BotSettings:
        record = BotSettingsRecord(
            id=1,
            bot_enabled=settings.bot_enabled,
            maintenance_mode=settings.maintenance_mode,
            antispam_enabled=settings.antispam_enabled,
            force_subscription_enabled=settings.force_subscription_enabled,
            offline_message=settings.offline_message,
            maintenance_message=settings.maintenance_message,
            updated_at=settings.updated_at,
        )
        self._session.add(record)
        await self._session.flush()
        return self._to_domain(record)

    async def update(self, settings: BotSettings) -> BotSettings:
        result = await self._session.execute(
            select(BotSettingsRecord).where(BotSettingsRecord.id == 1)
        )
        record = result.scalar_one_or_none()
        if record is None:
            return await self.create(settings)

        record.bot_enabled = settings.bot_enabled
        record.maintenance_mode = settings.maintenance_mode
        record.antispam_enabled = settings.antispam_enabled
        record.force_subscription_enabled = settings.force_subscription_enabled
        record.offline_message = settings.offline_message
        record.maintenance_message = settings.maintenance_message
        record.updated_at = settings.updated_at
        await self._session.flush()
        return self._to_domain(record)

    @staticmethod
    def _to_domain(record: BotSettingsRecord) -> BotSettings:
        return BotSettings(
            id=record.id,
            bot_enabled=record.bot_enabled,
            maintenance_mode=record.maintenance_mode,
            antispam_enabled=record.antispam_enabled,
            force_subscription_enabled=record.force_subscription_enabled,
            offline_message=record.offline_message,
            maintenance_message=record.maintenance_message,
            updated_at=record.updated_at,
        )
