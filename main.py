import asyncio
import logging
import os
from collections.abc import Iterable
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher

from config import (
    ADMIN_IDS,
    BOT_TOKEN,
    DATABASE_URL,
    MONITORING_ENABLED,
    MONITORING_INTERVAL_SECONDS,
)
from core.commands import setup_bot_commands
from core.database import Database
from core.errors import handle_error
from core.health import start_health_server, stop_health_server
from core.log_buffer import ErrorLogBuffer
from core.monitoring_runner import start_monitoring, stop_monitoring
from core.telegram import AiogramTelegramGateway
from core.transaction import SessionTransactionManager
from handlers.admin import router as admin_router
from handlers.admin_broadcast import router as admin_broadcast_router
from handlers.admin_cancel import router as admin_cancel_router
from handlers.admin_force_subscription import router as admin_force_subscription_router
from handlers.admin_force_subscription_stats import router as admin_force_subscription_stats_router
from handlers.admin_management import router as admin_management_router
from handlers.admin_referral_stats import router as admin_referral_stats_router
from handlers.admin_ai_monitoring import router as admin_ai_monitoring_router
from handlers.admin_settings import router as admin_settings_router
from handlers.admin_stats_refresh import router as admin_stats_refresh_router
from handlers.admin_support import router as admin_support_router
from handlers.admin_support_settings import router as admin_support_settings_router
from handlers.admin_system_stats import router as admin_system_stats_router
from handlers.force_subscription import router as force_subscription_router
from handlers.profile import router as profile_router
from handlers.referral import router as referral_router
from handlers.register import router as register_router
from handlers.start import router as start_router
from handlers.support import router as support_router
from middlewares.anti_spam import AntiSpamMiddleware
from middlewares.force_subscription import ForceSubscriptionMiddleware
from middlewares.logging import LoggingMiddleware
from middlewares.maintenance import MaintenanceMiddleware
from middlewares.services import ServicesMiddleware
from middlewares.user import UserMiddleware
from models.admin import AdminStatus
from repositories.admin import AdminRepository
from repositories.ai import AIProviderRepository, AIReportRepository
from repositories.antispam import AntiSpamRepository
from repositories.bot_settings import BotSettingsRepository
from repositories.user import UserRepository
from services.admin import AdminService
from services.ai import AIRouter
from services.monitoring import MonitoringService
from services.monitoring.analysis import AIAnalyzer
from services.system import SystemService


async def bootstrap_admin_system(database: Database) -> Iterable[int]:
    """Seed configured owners, synchronize capabilities, and return active admins."""
    async with database.get_session() as session:
        transaction_manager = SessionTransactionManager(session)
        admin_service = AdminService(
            admin_repository=AdminRepository(session),
            user_repository=UserRepository(session),
            transaction_manager=transaction_manager,
        )
        await admin_service.bootstrap(ADMIN_IDS)
        admins = await admin_service.list_admins()
        return tuple(
            admin.telegram_id
            for admin in admins
            if admin.status is AdminStatus.ACTIVE
        )


def build_monitoring_service(
    *,
    database: Database,
    system_service: SystemService,
    log_buffer: ErrorLogBuffer,
    bot: Bot,
) -> MonitoringService:
    """Wire the background monitor with its own per-cycle repository scope."""

    @asynccontextmanager
    async def repository_scope():
        async with database.get_session() as session:
            yield UserRepository(session), AntiSpamRepository(session)

    # AI bookkeeping (usage counters, reports) writes, so these scopes commit.
    @asynccontextmanager
    async def provider_scope():
        async with database.get_session() as session:
            async with session.begin():
                yield AIProviderRepository(session)

    @asynccontextmanager
    async def analysis_scope():
        async with database.get_session() as session:
            async with session.begin():
                yield AIReportRepository(session), BotSettingsRepository(session)

    async def active_admin_ids() -> tuple[int, ...]:
        async with database.get_session() as session:
            admin_repository = AdminRepository(session)
            admins = await admin_repository.list_admins()
        return tuple(
            admin.telegram_id for admin in admins if admin.status is AdminStatus.ACTIVE
        )

    analyzer = AIAnalyzer(
        router=AIRouter(repository_factory=provider_scope),
        repository_factory=analysis_scope,
    )
    return MonitoringService(
        system_service=system_service,
        log_buffer=log_buffer,
        telegram_gateway=AiogramTelegramGateway(bot),
        repository_factory=repository_scope,
        admin_ids_provider=active_admin_ids,
        analyzer=analyzer,
    )


async def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    # Keep recent warnings/errors in memory for the health monitor.
    log_buffer = ErrorLogBuffer()
    logging.getLogger().addHandler(log_buffer)
    # aiogram logs one "Update ... is handled" line per update at INFO;
    # keep only warnings/errors from it unless debugging.
    logging.getLogger("aiogram.event").setLevel(
        os.getenv("AIOGRAM_EVENT_LOG_LEVEL", "WARNING").upper()
    )

    logging.info("Bot starting...")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.errors.register(handle_error)

    database = Database(database_url=DATABASE_URL)
    system_service = SystemService(database=database)
    health_runner = await start_health_server()
    monitoring_task = None

    try:
        active_admin_ids = await bootstrap_admin_system(database)
        await setup_bot_commands(bot, active_admin_ids)

        # Always built so the admin panel can run "analyse now"; the
        # background loop itself is opt-in via MONITORING_ENABLED.
        monitoring_service = build_monitoring_service(
            database=database,
            system_service=system_service,
            log_buffer=log_buffer,
            bot=bot,
        )
        if MONITORING_ENABLED:
            monitoring_task = start_monitoring(
                monitoring_service, interval_seconds=MONITORING_INTERVAL_SECONDS
            )
            # Fast path: serious log errors trigger an out-of-band cycle.
            monitoring_service.attach_log_buffer()

        dp.update.middleware(LoggingMiddleware(system_service=system_service))
        dp.update.middleware(
            ServicesMiddleware(
                database=database,
                system_service=system_service,
                monitoring_service=monitoring_service,
            )
        )
        dp.update.middleware(MaintenanceMiddleware())
        dp.update.middleware(UserMiddleware())
        dp.update.middleware(ForceSubscriptionMiddleware())

        dp.message.outer_middleware(AntiSpamMiddleware())
        dp.callback_query.outer_middleware(AntiSpamMiddleware())

        dp.include_routers(
            start_router,
            register_router,
            profile_router,
            referral_router,
            support_router,
            force_subscription_router,
            admin_system_stats_router,
            admin_force_subscription_stats_router,
            admin_referral_stats_router,
            admin_stats_refresh_router,
            admin_management_router,
            admin_router,
            admin_cancel_router,
            admin_broadcast_router,
            admin_settings_router,
            admin_ai_monitoring_router,
            admin_force_subscription_router,
            admin_support_settings_router,
            admin_support_router,
        )

        await dp.start_polling(bot)
    finally:
        await stop_monitoring(monitoring_task)
        await stop_health_server(health_runner)
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(main())
