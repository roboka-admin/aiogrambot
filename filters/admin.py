from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message

from services.admin import AdminService


class AdminFilter(Filter):
    """Allow access only to active administrators stored in the database."""

    async def __call__(
        self,
        event: Message | CallbackQuery,
        admin_service: AdminService,
    ) -> bool:
        if event.from_user is None:
            return False
        return await admin_service.is_active_admin(event.from_user.id)
