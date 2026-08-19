from math import ceil

from exceptions.user import UserNotFoundError
from models.user import User
from repositories.interfaces.user import IUserRepository


class UserService:
    """Handles general user-related business operations."""

    def __init__(self, *, user_repository: IUserRepository) -> None:
        self._user_repository = user_repository

    async def exists(self, telegram_id: int) -> bool:
        return await self._user_repository.exists(telegram_id)

    async def get_user(self, telegram_id: int) -> User:
        user = await self._user_repository.get_by_telegram_id(telegram_id)
        if user is None:
            raise UserNotFoundError()
        return user

    async def get_users_page(
        self,
        *,
        page: int,
        page_size: int,
    ) -> tuple[list[User], int, int]:
        total = await self._user_repository.count()
        total_pages = max(1, ceil(total / page_size))
        page = min(max(page, 0), total_pages - 1)

        users = await self._user_repository.list_page(
            offset=page * page_size,
            limit=page_size,
        )
        return users, total, page

    async def update_name(self, telegram_id: int, name: str) -> User:
        user = await self.get_user(telegram_id)
        user.name = name.strip()
        updated_user = await self._user_repository.update(user)
        assert updated_user is not None
        return updated_user

    async def update_age(self, telegram_id: int, age: int) -> User:
        user = await self.get_user(telegram_id)
        user.age = age
        updated_user = await self._user_repository.update(user)
        assert updated_user is not None
        return updated_user
