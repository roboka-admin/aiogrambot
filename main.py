import asyncio
import logging

from aiogram import Bot, Dispatcher

from handlers.start import router as start_router
from handlers.register import router as register_router

from middlewares.logging import LoggingMiddleware
from middlewares.services import ServicesMiddleware

from repositories.user import UserRepository
from services.register import RegisterService
from config import TOKEN



async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    logging.info("Bot starting...")

    bot = Bot(token=TOKEN)

    dp = Dispatcher()

    # =========================
    # Repositories
    # =========================

    user_repository = UserRepository()

    # =========================
    # Services
    # =========================

    register_service = RegisterService(
        user_repository=user_repository
    )

    # =========================
    # Middlewares
    # =========================

    dp.update.middleware(
        LoggingMiddleware()
    )

    dp.update.middleware(
        ServicesMiddleware(
            register_service=register_service,
        )
    )

    # =========================
    # Routers
    # =========================

    dp.include_router(start_router)
    dp.include_router(register_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())