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
        patch("middlewares.services.RegisterService") as register_service,
        patch("middlewares.services.UserService") as user_service,
        patch("middlewares.services.SupportService") as support_service,
        patch("middlewares.services.BroadcastService") as broadcast_service,
        patch("middlewares.services.AntiSpamService") as antispam_service,
        patch("middlewares.services.NotificationService") as notification_service,
    ):
        middleware = ServicesMiddleware(
            database=database,
            system_service=system_service,
        )

        result = await middleware(handler, MagicMock(), data)

    assert result == "handled"
    session.begin.assert_called_once_with()
    assert database.transaction.exited_with is None

    user_repository.assert_called_once_with(session)
    support_repository.assert_called_once_with(session)
    broadcast_repository.assert_called_once_with(session)
    antispam_repository.assert_called_once_with(session)

    register_service.assert_called_once_with(
        user_repository=user_repository.return_value,
    )
    user_service.assert_called_once_with(
        user_repository=user_repository.return_value,
    )
    support_service.assert_called_once_with(
        support_repository=support_repository.return_value,
    )
    broadcast_service.assert_called_once_with(
        user_repository=user_repository.return_value,
        broadcast_repository=broadcast_repository.return_value,
        bot=bot,
    )
    antispam_service.assert_called_once_with(
        antispam_repository=antispam_repository.return_value,
    )
    notification_service.assert_called_once_with(bot=bot)

    assert data["register_service"] is register_service.return_value
    assert data["user_service"] is user_service.return_value
    assert data["support_service"] is support_service.return_value
    assert data["broadcast_service"] is broadcast_service.return_value
    assert data["antispam_service"] is antispam_service.return_value
    assert data["notification_service"] is notification_service.return_value
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
        patch("middlewares.services.RegisterService"),
        patch("middlewares.services.UserService"),
        patch("middlewares.services.SupportService"),
        patch("middlewares.services.BroadcastService"),
        patch("middlewares.services.AntiSpamService"),
        patch("middlewares.services.NotificationService"),
    ):
        middleware = ServicesMiddleware(
            database=database,
            system_service=system_service,
        )
        with pytest.raises(RuntimeError, match="handler failed"):
            await middleware(handler, MagicMock(), {"bot": bot})

    assert database.transaction.exited_with is RuntimeError
