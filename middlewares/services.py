import asyncio
from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from config import ADMIN_IDS
from core.admin_permissions import ADMIN_PERMISSION_REGISTRY
from core.database import Database
from repositories.admin import AdminRepository
from repositories.antispam import AntiSpamRepository
from repositories.bot_settings import BotSettingsRepository
from repositories.broadcast import BroadcastRepository
from repositories.force_subscription import ForceSubscriptionRepository
from repositories.force_subscription_event import ForceSubscriptionEventRepository
from repositories.support import SupportRepository
from repositories.user import UserRepository
from services.admin import AdminService
from services.antispam import AntiSpamService
from services.bot_settings import BotSettingsService
from services.broadcast import BroadcastService
from services.force_subscription import ForceSubscriptionService
from services.notification import NotificationService
from services.register import RegisterService
from services.support import SupportService
from services.system import SystemService
from services.user import UserService


class ServicesMiddleware(BaseMiddleware):
    """Create request-scoped repository and services."""

    def __init__(self, *, database: Database, system_service: SystemService) -> None:
        self._database = database
        self._system_service = system_service
        self._broadcast_lock = asyncio.Lock()
        self._admin_registry_lock = asyncio.Lock()
        self._admin_registry_synced = False

    async def _ensure_admin_registry(self) -> None:
        if self._admin_registry_synced:
            return
        async with self._admin_registry_lock:
            if self._admin_registry_synced:
                return
            async with self._database.get_session() as session:
                async with session.begin():
                    admin_repository = AdminRepository(session)
                    admin_service = AdminService(admin_repository=admin_repository)
                    await admin_service.sync_permission_registry(
                        ADMIN_PERMISSION_REGISTRY
                    )
                    for telegram_id in ADMIN_IDS:
                        await admin_service.ensure_owner(telegram_id)
            # Only mark the registry ready after its transaction has committed.
            self._admin_registry_synced = True

    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]], event: TelegramObject, data: dict[str, Any]) -> Any:
        await self._ensure_admin_registry()

        async with self._database.get_session() as session:
            async with session.begin():
                user_repository = UserRepository(session)
                support_repository = SupportRepository(session)
                antispam_repository = AntiSpamRepository(session)
                bot_settings_repository = BotSettingsRepository(session)
                force_subscription_repository = ForceSubscriptionRepository(session)
                force_subscription_event_repository = ForceSubscriptionEventRepository(session)
                admin_repository = AdminRepository(session)

                @asynccontextmanager
                async def broadcast_repository_scope():
                    async with self._database.get_session() as broadcast_session:
                        async with broadcast_session.begin():
                            yield (UserRepository(broadcast_session), BroadcastRepository(broadcast_session))

                register_service = RegisterService(user_repository=user_repository)
                user_service = UserService(user_repository=user_repository)
                support_service = SupportService(support_repository=support_repository)
                bot_settings_service = BotSettingsService(bot_settings_repository=bot_settings_repository)
                broadcast_service = BroadcastService(bot=data["bot"], repository_factory=broadcast_repository_scope, broadcast_lock=self._broadcast_lock)
                antispam_service = AntiSpamService(antispam_repository=antispam_repository)
                force_subscription_service = ForceSubscriptionService(
                    bot=data["bot"],
                    repository=force_subscription_repository,
                    event_repository=force_subscription_event_repository,
                )
                notification_service = NotificationService(bot=data["bot"])
                admin_service = AdminService(admin_repository=admin_repository)

                data["register_service"] = register_service
                data["user_service"] = user_service
                data["support_service"] = support_service
                data["bot_settings_service"] = bot_settings_service
                data["broadcast_service"] = broadcast_service
                data["antispam_service"] = antispam_service
                data["force_subscription_service"] = force_subscription_service
                data["notification_service"] = notification_service
                data["admin_service"] = admin_service
                data["system_service"] = self._system_service

                return await handler(event, data)
