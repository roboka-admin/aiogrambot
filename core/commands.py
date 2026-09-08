from collections.abc import Iterable

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat


PUBLIC_COMMANDS: tuple[BotCommand, ...] = (
    BotCommand(command="start", description="شروع کار با ربات"),
)

ADMIN_COMMANDS: tuple[BotCommand, ...] = (
    *PUBLIC_COMMANDS,
    BotCommand(command="admin", description="پنل مدیریت"),
)


async def setup_bot_commands(bot: Bot, admin_telegram_ids: Iterable[int]) -> None:
    """Register the public command menu and the admin menu for active admins."""
    await bot.set_my_commands(list(PUBLIC_COMMANDS))
    for telegram_id in admin_telegram_ids:
        await set_admin_commands(bot, telegram_id)


async def set_admin_commands(bot: Bot, telegram_id: int) -> None:
    """Expose admin commands only in the specified admin's private chat."""
    await bot.set_my_commands(
        list(ADMIN_COMMANDS),
        scope=BotCommandScopeChat(chat_id=telegram_id),
    )


async def remove_admin_commands(bot: Bot, telegram_id: int) -> None:
    """Remove the admin-specific command menu from a user's chat."""
    await bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=telegram_id))
