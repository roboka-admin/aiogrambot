import asyncio
import logging
import os

from aiogram import Bot, Dispatcher

from core.database import Database
from handlers.start import router as start_router
from handlers.register import router as register_router
from middlewares.logging import LoggingMiddleware
from middlewares.services import ServicesMiddleware
from config import TOKEN


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    logging.info("Bot starting...")

    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    database = Database(
        database_url=os.getenv(
            "DATABASE_URL",
            "sqlite+aiosqlite:///./bot.db",
        ),
    )

    await database.create_tables()

    dp.update.middleware(LoggingMiddleware())
    dp.update.middleware(ServicesMiddleware(database=database))

    dp.include_router(start_router)
    dp.include_router(register_router)

    try:
        await dp.start_polling(bot)
    finally:
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(main())
