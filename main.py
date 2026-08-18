import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN, DATABASE_URL
from core.database import Database
from handlers.edit_profile import router as edit_profile_router
from handlers.profile import router as profile_router
from handlers.register import router as register_router
from handlers.start import router as start_router
from middlewares.logging import LoggingMiddleware
from middlewares.services import ServicesMiddleware


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    logging.info("Bot starting...")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    database = Database(database_url=DATABASE_URL)
    await database.create_tables()

    dp.update.middleware(LoggingMiddleware())
    dp.update.middleware(ServicesMiddleware(database=database))

    dp.include_router(start_router)
    dp.include_router(register_router)
    dp.include_router(profile_router)
    dp.include_router(edit_profile_router)

    try:
        await dp.start_polling(bot)
    finally:
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(main())
