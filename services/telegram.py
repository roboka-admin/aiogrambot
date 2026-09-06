from dataclasses import dataclass
from typing import Protocol


class TelegramGatewayError(Exception):
    """Base error raised when the Telegram gateway cannot complete an operation."""


class TelegramAccessError(TelegramGatewayError):
    """The bot cannot access the requested Telegram resource."""


class TelegramRateLimitError(TelegramGatewayError):
    """Telegram asked the caller to wait before retrying."""

    def __init__(self, retry_after: int) -> None:
        super().__init__(f"Telegram rate limit; retry after {retry_after} seconds")
        self.retry_after = retry_after


@dataclass(frozen=True, slots=True)
class TelegramChat:
    id: int
    type: str
    title: str | None
    username: str | None
    invite_link: str | None


class TelegramGateway(Protocol):
    async def copy_message(
        self,
        *,
        chat_id: int,
        from_chat_id: int,
        message_id: int,
    ) -> None: ...

    async def get_chat(self, *, chat_id: int | str) -> TelegramChat: ...

    async def get_chat_member(self, *, chat_id: int, user_id: int) -> str: ...

    async def send_message(self, telegram_id: int, text: str) -> None: ...
