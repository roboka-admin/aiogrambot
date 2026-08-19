from aiogram.filters import Filter
from aiogram.types import Message

from config import ADMIN_IDS


class AdminFilter(Filter):
    """Allow access only to configured administrators."""

    async def __call__(self, message: Message) -> bool:
        return (
            message.from_user is not None
            and message.from_user.id in ADMIN_IDS
        )
