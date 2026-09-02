from core.timezone import tehran_now
from models.bot_settings import BotSettings
from repositories.interfaces.bot_settings import IBotSettingsRepository


class BotSettingsService:
    def __init__(self, *, bot_settings_repository: IBotSettingsRepository) -> None:
        self._bot_settings_repository = bot_settings_repository

    async def get_settings(self) -> BotSettings:
        settings = await self._bot_settings_repository.get()
        if settings is not None:
            return settings
        return await self._bot_settings_repository.create(BotSettings())

    async def set_bot_enabled(self, enabled: bool) -> BotSettings:
        settings = await self.get_settings()
        settings.bot_enabled = enabled
        settings.updated_at = tehran_now()
        return await self._bot_settings_repository.update(settings)

    async def set_maintenance_mode(self, enabled: bool) -> BotSettings:
        settings = await self.get_settings()
        settings.maintenance_mode = enabled
        settings.updated_at = tehran_now()
        return await self._bot_settings_repository.update(settings)

    async def toggle_bot(self) -> BotSettings:
        settings = await self.get_settings()
        settings.bot_enabled = not settings.bot_enabled
        settings.updated_at = tehran_now()
        return await self._bot_settings_repository.update(settings)

    async def toggle_maintenance(self) -> BotSettings:
        settings = await self.get_settings()
        settings.maintenance_mode = not settings.maintenance_mode
        settings.updated_at = tehran_now()
        return await self._bot_settings_repository.update(settings)
