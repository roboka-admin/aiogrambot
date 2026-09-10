from unittest.mock import AsyncMock, MagicMock

import pytest

from models.bot_settings import BotSettings
from services.bot_settings import BotSettingsService


@pytest.mark.asyncio
async def test_get_settings_returns_existing_settings() -> None:
    settings = BotSettings(bot_enabled=False, maintenance_mode=True)
    repository = MagicMock()
    repository.get = AsyncMock(return_value=settings)
    repository.create = AsyncMock()
    service = BotSettingsService(bot_settings_repository=repository)

    result = await service.get_settings()

    assert result is settings
    repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_settings_creates_defaults_when_missing() -> None:
    created = BotSettings()
    repository = MagicMock()
    repository.get = AsyncMock(return_value=None)
    repository.create = AsyncMock(return_value=created)
    service = BotSettingsService(bot_settings_repository=repository)

    result = await service.get_settings()

    assert result is created
    created_settings = repository.create.await_args.args[0]
    assert created_settings.bot_enabled is True
    assert created_settings.maintenance_mode is False
    assert created_settings.antispam_enabled is True


@pytest.mark.asyncio
async def test_toggle_bot_updates_existing_settings() -> None:
    settings = BotSettings(bot_enabled=True)
    repository = MagicMock()
    repository.get = AsyncMock(return_value=settings)
    repository.update = AsyncMock(side_effect=lambda value: value)
    service = BotSettingsService(bot_settings_repository=repository)

    result = await service.toggle_bot()

    assert result.bot_enabled is False
    repository.get.assert_awaited_once()
    repository.update.assert_awaited_once_with(settings)


@pytest.mark.asyncio
async def test_toggle_maintenance_updates_existing_settings() -> None:
    settings = BotSettings(maintenance_mode=False)
    repository = MagicMock()
    repository.get = AsyncMock(return_value=settings)
    repository.update = AsyncMock(side_effect=lambda value: value)
    service = BotSettingsService(bot_settings_repository=repository)

    result = await service.toggle_maintenance()

    assert result.maintenance_mode is True
    repository.get.assert_awaited_once()
    repository.update.assert_awaited_once_with(settings)


@pytest.mark.asyncio
async def test_toggle_antispam_updates_existing_settings() -> None:
    settings = BotSettings(antispam_enabled=True)
    repository = MagicMock()
    repository.get = AsyncMock(return_value=settings)
    repository.update = AsyncMock(side_effect=lambda value: value)
    service = BotSettingsService(bot_settings_repository=repository)

    result = await service.toggle_antispam()

    assert result.antispam_enabled is False
    repository.get.assert_awaited_once()
    repository.update.assert_awaited_once_with(settings)


@pytest.mark.asyncio
async def test_set_referral_reward_updates_both_values() -> None:
    settings = BotSettings()
    repository = MagicMock()
    repository.get = AsyncMock(return_value=settings)
    repository.update = AsyncMock(side_effect=lambda value: value)
    service = BotSettingsService(bot_settings_repository=repository)

    result = await service.set_referral_reward(coins=5, per_invites=3)

    assert result.referral_reward_coins == 5
    assert result.referral_reward_per_invites == 3
    repository.update.assert_awaited_once_with(settings)


@pytest.mark.asyncio
@pytest.mark.parametrize("coins, per_invites", [(0, 1), (1, 0), (-1, 1), (1, -3)])
async def test_set_referral_reward_rejects_non_positive_values(
    coins: int, per_invites: int
) -> None:
    repository = MagicMock()
    repository.get = AsyncMock(return_value=BotSettings())
    repository.update = AsyncMock()
    service = BotSettingsService(bot_settings_repository=repository)

    with pytest.raises(ValueError):
        await service.set_referral_reward(coins=coins, per_invites=per_invites)
    repository.update.assert_not_awaited()


def test_default_referral_reward_is_one_coin_per_invite() -> None:
    settings = BotSettings()

    assert settings.referral_reward_coins == 1
    assert settings.referral_reward_per_invites == 1
