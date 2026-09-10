from contextlib import asynccontextmanager, ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram import Bot

from middlewares.services import ServicesMiddleware


class FakeDatabase:
    def __init__(self, session):
        self.session = session

    @asynccontextmanager
    async def get_session(self):
        yield self.session


def _enter_service_patches(stack: ExitStack) -> dict[str, MagicMock]:
    names = (
        "UserRepository",
        "SupportRepository",
        "BroadcastRepository",
        "AntiSpamRepository",
        "BotSettingsRepository",
        "ForceSubscriptionRepository",
        "ForceSubscriptionEventRepository",
        "AdminRepository",
        "ReferralRepository",
        "AiogramTelegramGateway",
        "RegisterService",
        "UserService",
        "SupportService",
        "BotSettingsService",
        "BroadcastService",
        "AntiSpamService",
        "ForceSubscriptionService",
        "NotificationService",
        "AdminService",
        "ReferralService",
    )
    return {
        name: stack.enter_context(patch(f"middlewares.services.{name}"))
        for name in names
    }


@pytest.mark.asyncio
async def test_services_middleware_creates_and_injects_request_scoped_dependencies():
    session = MagicMock()
    database = FakeDatabase(session)
    system_service = MagicMock()
    bot = Bot("42:TEST")
    handler = AsyncMock(return_value="handled")
    data = {"bot": bot}

    with ExitStack() as stack:
        mocks = _enter_service_patches(stack)
        middleware = ServicesMiddleware(database=database, system_service=system_service)
        result = await middleware(handler, MagicMock(), data)

    assert result == "handled"
    session.begin.assert_not_called()
    transaction_manager = mocks["RegisterService"].call_args.kwargs["transaction_manager"]

    mocks["AiogramTelegramGateway"].assert_called_once_with(bot)
    mocks["UserRepository"].assert_called_once_with(session)
    mocks["SupportRepository"].assert_called_once_with(session)
    mocks["AntiSpamRepository"].assert_called_once_with(session)
    mocks["BotSettingsRepository"].assert_called_once_with(session)
    mocks["ForceSubscriptionRepository"].assert_called_once_with(session)
    mocks["ForceSubscriptionEventRepository"].assert_called_once_with(session)
    mocks["AdminRepository"].assert_called_once_with(session)
    mocks["ReferralRepository"].assert_called_once_with(session)
    mocks["BroadcastRepository"].assert_not_called()

    mocks["RegisterService"].assert_called_once_with(
        user_repository=mocks["UserRepository"].return_value,
        transaction_manager=transaction_manager,
    )
    mocks["UserService"].assert_called_once_with(
        user_repository=mocks["UserRepository"].return_value,
        transaction_manager=transaction_manager,
    )
    mocks["SupportService"].assert_called_once_with(
        support_repository=mocks["SupportRepository"].return_value,
        transaction_manager=transaction_manager,
    )
    mocks["BotSettingsService"].assert_called_once_with(
        bot_settings_repository=mocks["BotSettingsRepository"].return_value,
        transaction_manager=transaction_manager,
    )

    mocks["BroadcastService"].assert_called_once()
    broadcast_kwargs = mocks["BroadcastService"].call_args.kwargs
    assert broadcast_kwargs["telegram_gateway"] is mocks["AiogramTelegramGateway"].return_value
    assert callable(broadcast_kwargs["repository_factory"])
    assert broadcast_kwargs["broadcast_lock"] is middleware._broadcast_lock

    mocks["AntiSpamService"].assert_called_once_with(
        antispam_repository=mocks["AntiSpamRepository"].return_value,
        transaction_manager=transaction_manager,
    )
    mocks["ForceSubscriptionService"].assert_called_once_with(
        telegram_gateway=mocks["AiogramTelegramGateway"].return_value,
        repository=mocks["ForceSubscriptionRepository"].return_value,
        event_repository=mocks["ForceSubscriptionEventRepository"].return_value,
        transaction_manager=transaction_manager,
    )
    mocks["NotificationService"].assert_called_once_with(
        telegram_gateway=mocks["AiogramTelegramGateway"].return_value
    )
    mocks["AdminService"].assert_called_once_with(
        admin_repository=mocks["AdminRepository"].return_value,
        user_repository=mocks["UserRepository"].return_value,
        transaction_manager=transaction_manager,
    )
    mocks["ReferralService"].assert_called_once_with(
        referral_repository=mocks["ReferralRepository"].return_value,
        bot_settings_repository=mocks["BotSettingsRepository"].return_value,
        transaction_manager=transaction_manager,
    )

    assert data["register_service"] is mocks["RegisterService"].return_value
    assert data["user_service"] is mocks["UserService"].return_value
    assert data["support_service"] is mocks["SupportService"].return_value
    assert data["bot_settings_service"] is mocks["BotSettingsService"].return_value
    assert data["broadcast_service"] is mocks["BroadcastService"].return_value
    assert data["antispam_service"] is mocks["AntiSpamService"].return_value
    assert data["force_subscription_service"] is mocks["ForceSubscriptionService"].return_value
    assert data["notification_service"] is mocks["NotificationService"].return_value
    assert data["admin_service"] is mocks["AdminService"].return_value
    assert data["referral_service"] is mocks["ReferralService"].return_value
    assert data["system_service"] is system_service
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_services_middleware_does_not_create_transaction_for_handler():
    session = MagicMock()
    database = FakeDatabase(session)
    system_service = MagicMock()
    bot = Bot("42:TEST")

    async def handler(event, data):
        raise RuntimeError("handler failed")

    with ExitStack() as stack:
        _enter_service_patches(stack)
        middleware = ServicesMiddleware(database=database, system_service=system_service)
        with pytest.raises(RuntimeError, match="handler failed"):
            await middleware(handler, MagicMock(), {"bot": bot})

    session.begin.assert_not_called()
