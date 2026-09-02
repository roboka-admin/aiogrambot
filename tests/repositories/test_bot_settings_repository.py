import pytest

from models.bot_settings import BotSettings
from repositories.bot_settings import BotSettingsRepository


@pytest.mark.asyncio
async def test_bot_settings_repository_create_get_and_update(session):
    repository = BotSettingsRepository(session)

    assert await repository.get() is None

    created = await repository.create(BotSettings())
    assert created.id == 1
    assert created.bot_enabled is True
    assert created.maintenance_mode is False

    created.bot_enabled = False
    created.maintenance_mode = True
    updated = await repository.update(created)

    assert updated.bot_enabled is False
    assert updated.maintenance_mode is True

    loaded = await repository.get()
    assert loaded is not None
    assert loaded.id == 1
    assert loaded.bot_enabled is False
    assert loaded.maintenance_mode is True
