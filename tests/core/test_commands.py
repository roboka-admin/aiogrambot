from unittest.mock import AsyncMock

import pytest
from aiogram.types import BotCommandScopeChat

from core.commands import ADMIN_COMMANDS, PUBLIC_COMMANDS, remove_admin_commands, set_admin_commands, setup_bot_commands


@pytest.mark.asyncio
async def test_setup_bot_commands_registers_public_and_admin_scopes() -> None:
    bot = AsyncMock()

    await setup_bot_commands(bot, [10, 20])

    bot.set_my_commands.assert_any_await(list(PUBLIC_COMMANDS))
    assert bot.set_my_commands.await_count == 3
    bot.set_my_commands.assert_any_await(
        list(ADMIN_COMMANDS), scope=BotCommandScopeChat(chat_id=10)
    )
    bot.set_my_commands.assert_any_await(
        list(ADMIN_COMMANDS), scope=BotCommandScopeChat(chat_id=20)
    )


@pytest.mark.asyncio
async def test_set_admin_commands_uses_private_chat_scope() -> None:
    bot = AsyncMock()

    await set_admin_commands(bot, 123)

    bot.set_my_commands.assert_awaited_once_with(
        list(ADMIN_COMMANDS), scope=BotCommandScopeChat(chat_id=123)
    )


@pytest.mark.asyncio
async def test_remove_admin_commands_deletes_private_chat_scope() -> None:
    bot = AsyncMock()

    await remove_admin_commands(bot, 123)

    bot.delete_my_commands.assert_awaited_once_with(
        scope=BotCommandScopeChat(chat_id=123)
    )
