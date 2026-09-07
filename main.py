import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import ADMIN_IDS, BOT_TOKEN, DATABASE_URL
from core.database import Database
from core.transaction import SessionTransactionManager
from handlers.admin import router as admin_router
from handlers.admin_broadcast import router as admin_broadcast_router
from handlers.admin_cancel import router as admin_cancel_router
from handlers.admin_force_subscription import router as admin_force_subscription_router
from handlers.admin_force_subscription_stats import router as admin_force_subscription_stats_router
from handlers.admin_management import router as admin_management_router
from handlers.admin_settings import router as admin_settings_router
from handlers.admin_stats_refresh import router as admin_stats_refresh_router
from handlers.admin_support import router as admin_support_router
from handlers.admin_support_settings import router as admin_support_settings_router
from handlers.admin_system_stats import router as admin_system_stats_router
from handlers.edit_profile import router as edit_profile_router
from handlers.force_subscription import router as force_subscription_router
from handlers.profile import router as profile_router
from handlers.register import router as register_router
from handlers.start import router as start_router
from handlers.support import router as support_router
from middlewares.anti_spam import AntiSpamMiddleware
from middlewares.force_subscription import ForceSubscriptionMiddleware
from middlewares.logging import LoggingMiddleware
from middlewares.maintenance import MaintenanceMiddleware
from middlewares.services import ServicesMiddleware
from middlewares.user import UserMiddleware
from repositories.admin import AdminRepository
from repositories.user import UserRepository
from services.admin import AdminService
from services.system import SystemService


async def bootstrap_admin_system(database: Database) -> None:
    """Seed configured owners and synchronize admin capabilities at startup."""
    async with database.get_session() as session:
        transaction_manager = SessionTransactionManager(session)
        admin_service = AdminService(
            admin_repository=AdminRepository(session),
            user_repository=UserRepository(session),
            transaction_manager=transaction_manager,
        )
        await admin_service.bootstrap(ADMIN_IDS)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    logging.info("Bot starting...")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    database = Database(database_url=DATABASE_URL)
    system_service = SystemService(database=database)

    try:
        await bootstrap_admin_system(database)

        dp.update.middleware(LoggingMiddleware(system_service=system_service))
        dp.update.middleware(ServicesMiddleware(database=database, system_service=system_service))
        dp.update.middleware(MaintenanceMiddleware())
        dp.update.middleware(UserMiddleware())
        dp.update.middleware(ForceSubscriptionMiddleware())

        dp.message.outer_middleware(AntiSpamMiddleware())
        dp.callback_query.outer_middleware(AntiSpamMiddleware())

        dp.include_router(start_router)
        dp.include_router(register_router)
        dp.include_router(profile_router)
        dp.include_router(support_router)
        dp.include_router(edit_profile_router)
        dp.include_router(force_subscription_router)
        dp.include_router(admin_system_stats_router)
        dp.include_router(admin_force_subscription_stats_router)
        dp.include_router(admin_stats_refresh_router)
        dp.include_router(admin_management_router)
        dp.include_router(admin_router)
        dp.include_router(admin_cancel_router)
        dp.include_router(admin_broadcast_router)
        dp.include_router(admin_settings_router)
        dp.include_router(admin_force_subscription_router)
        dp.include_router(admin_support_settings_router)
        dp.include_router(admin_support_router)

        await dp.start_polling(bot)
    finally:
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(main())
