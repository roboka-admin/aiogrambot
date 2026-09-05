from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram import Bot

from middlewares.services import ServicesMiddleware


class TransactionContext:
    def __init__(self):
        self.exited_with = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.exited_with = exc_type
        return False


class FakeDatabase:
    def __init__(self, session):
        self.session = session
        self.transaction = TransactionContext()

    @asynccontextmanager
    async def get_session(self):
        yield self.session


@pytest.mark.asyncio
async def test_services_middleware_creates_and_injects_request_scoped_dependencies():
    session = MagicMock()
    database = FakeDatabase(session)
    session.begin.return_value = database.transaction
    system_service = MagicMock()
    bot = Bot("42:TEST")
    handler = AsyncMock(return_value="handled")
    data = {"bot": bot}

    with (
        patch("middlewares.services.UserRepository") as user_repository,
        patch("middlewares.services.SupportRepository") as support_repository,
        patch("middlewares.services.BroadcastRepository") as broadcast_repository,
        patch("middlewares.services.AntiSpamRepository") as antispam_repository,
        patch("middlewares.services.BotSettingsRepository") as bot_settings_repository,
        patch("middlewares.services.ForceSubscriptionRepository") as force_subscription_repository,
        patch("middlewares.services.ForceSubscriptionEventRepository") as force_subscription_event_repository,
        patch("middlewares.services.AdminRepository") as admin_repository,
        patch("middlewares.services.RegisterService") as register_service,
        patch("middlewares.services.UserService") as user_service,
        patch("middlewares.services.SupportService") as support_service,
        patch("middlewares.services.BotSettingsService") as bot_settings_service,
        patch("middlewares.services.BroadcastService") as broadcast_service,
        patch("middlewares.services.AntiSpamService") as antispam_service,
        patch("middlewares.services.ForceSubscriptionService") as force_subscription_service,
        patch("middlewares.services.NotificationService") as notification_service,
        patch("middlewares.services.AdminService") as admin_service,
    ):
        middleware = ServicesMiddleware(
            database=database,
            system_service=system_service,
        )

        result = await middleware(handler, MagicMock(), data)

    assert result == "handled"
    assert session.begin.call_count == 2
    assert database.transaction.exited_with is None

    user_repository.assert_called_once_with(session)
    support_repository.assert_called_once_with(session)
    antispam_repository.assert_called_once_with(session)
    bot_settings_repository.assert_called_once_with(session)
    force_subscription_repository.assert_called_once_with(session)
    force_subscription_event_repository.assert_called_once_with(session)
    admin_repository.assert_any_call(session)
    broadcast_repository.assert_not_called()

    register_service.assert_called_once_with(
        user_repository=user_repository.return_value,
    )
    user_service.assert_called_once_with(
        user_repository=user_repository.return_value,
    )
    support_service.assert_called_once_with(
        support_repository=support_repository.return_value,
    )
    bot_settings_service.assert_called_once_with(
        bot_settings_repository=bot_settings_repository.return_value,
    )
    broadcast_service.assert_called_once()
    broadcast_service_kwargs = broadcast_service.call_args.kwargs
    assert broadcast_service_kwargs["bot"] is bot
    assert callable(broadcast_service_kwargs["repository_factory"])
    assert broadcast_service_kwargs["broadcast_lock"] is middleware._broadcast_lock
    antispam_service.assert_called_once_with(
        antispam_repository=antispam_repository.return_value,
    )
    force_subscription_service.assert_called_once_with(
        bot=bot,
        repository=force_subscription_repository.return_value,
        event_repository=force_subscription_event_repository.return_value,
    )
    notification_service.assert_called_once_with(bot=bot)
    admin_service.assert_called_once_with(
        admin_repository=admin_repository.return_value,
    )
    admin_service.return_value.sync_permission_registry.assert_awaited_once_with(
        __import__("core.admin_permissions", fromlist=["ADMIN_PERMISSION_REGISTRY"]).ADMIN_PERMISSION_REGISTRY
    )

    assert data["register_service"] is register_service.return_value
    assert data["user_service"] is user_service.return_value
    assert data["support_service"] is support_service.return_value
    assert data["bot_settings_service"] is bot_settings_service.return_value
    assert data["broadcast_service"] is broadcast_service.return_value
    assert data["antispam_service"] is antispam_service.return_value
    assert data["force_subscription_service"] is force_subscription_service.return_value
    assert data["notification_service"] is notification_service.return_value
    assert data["admin_service"] is admin_service.return_value
    assert data["system_service"] is system_service
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_services_middleware_passes_handler_exception_through_transaction():
    session = MagicMock()
    database = FakeDatabase(session)
    session.begin.return_value = database.transaction
    system_service = MagicMock()
    bot = Bot("42:TEST")

    async def handler(event, data):
        raise RuntimeError("handler failed")

    with (
        patch("middlewares.services.UserRepository"),
        patch("middlewares.services.SupportRepository"),
        patch("middlewares.services.BroadcastRepository"),
        patch("middlewares.services.AntiSpamRepository"),
        patch("middlewares.services.BotSettingsRepository"),
        patch("middlewares.services.ForceSubscriptionRepository"),
        patch("middlewares.services.ForceSubscriptionEventRepository"),
        patch("middlewares.services.AdminRepository") as admin_repository,
        patch("middlewares.services.RegisterService"),
        patch("middlewares.services.UserService"),
        patch("middlewares.services.SupportService"),
        patch("middlewares.services.BotSettingsService"),
        patch("middlewares.services.BroadcastService"),
        patch("middlewares.services.AntiSpamService"),
        patch("middlewares.services.ForceSubscriptionService"),
        patch("middlewares.services.NotificationService"),
        patch("middlewares.services.AdminService") as admin_service,
    ):
        middleware = ServicesMiddleware(
            database=database,
            system_service=system_service,
        )
        with pytest.raises(RuntimeError, match="handler failed"):
            await middleware(handler, MagicMock(), {"bot": bot})

    admin_repository.assert_any_call(session)
    admin_service.assert_called_once_with(
        admin_repository=admin_repository.return_value,
    )
    assert database.transaction.exited_with is RuntimeError
