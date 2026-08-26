from math import ceil

from exceptions.user import UserNotFoundError
from models.user import RegistrationStatus, User, UserStatus
from repositories.interfaces.user import IUserRepository

_MAX_WARNINGS = 3


class UserService:
    def __init__(self, *, user_repository: IUserRepository) -> None:
        self._user_repository = user_repository

    async def get_or_create_telegram_user(self, *, telegram_id: int, telegram_name: str, username: str | None) -> User:
        user = await self._user_repository.get_by_telegram_id(telegram_id)
        if user is None:
            return await self._user_repository.create(User(telegram_id=telegram_id, telegram_name=telegram_name, username=username))
        user.telegram_name = telegram_name
        user.username = username
        return await self._save(user)

    async def exists(self, telegram_id: int) -> bool:
        return await self._user_repository.exists(telegram_id)

    async def get_user(self, telegram_id: int) -> User:
        user = await self._user_repository.get_by_telegram_id(telegram_id)
        if user is None:
            raise UserNotFoundError()
        return user

    async def get_users_page(self, *, page: int, page_size: int) -> tuple[list[User], int, int]:
        total = await self._user_repository.count()
        total_pages = max(1, ceil(total / page_size))
        page = min(max(page, 0), total_pages - 1)
        return await self._user_repository.list_page(offset=page * page_size, limit=page_size), total, page

    async def get_user_counts(self) -> dict[str, int]:
        return {
            "total": await self._user_repository.count(),
            "registered": await self._user_repository.count_registered(),
            "unregistered": await self._user_repository.count_unregistered(),
            "blocked": await self._user_repository.count_blocked(),
        }

    async def update_name(self, telegram_id: int, name: str) -> User:
        user = await self.get_user(telegram_id)
        user.name = name.strip()
        return await self._save(user)

    async def update_age(self, telegram_id: int, age: int) -> User:
        user = await self.get_user(telegram_id)
        user.age = age
        return await self._save(user)

    async def complete_registration(self, *, telegram_id: int, name: str, age: int) -> User:
        user = await self.get_user(telegram_id)
        if user.registration_status == RegistrationStatus.REGISTERED:
            raise ValueError("User is already registered")
        user.name = name.strip()
        user.age = age
        user.registration_status = RegistrationStatus.REGISTERED
        return await self._save(user)

    async def add_coins(self, telegram_id: int, amount: int = 1) -> User:
        if amount <= 0: raise ValueError("Amount must be positive")
        user = await self.get_user(telegram_id); user.coins += amount
        return await self._save(user)

    async def remove_coins(self, telegram_id: int, amount: int = 1) -> User:
        if amount <= 0: raise ValueError("Amount must be positive")
        user = await self.get_user(telegram_id); user.coins = max(0, user.coins - amount)
        return await self._save(user)

    async def add_warning(self, telegram_id: int) -> User:
        user = await self.get_user(telegram_id); user.warnings += 1
        if user.warnings >= _MAX_WARNINGS: user.status = UserStatus.BLOCKED
        return await self._save(user)

    async def block_user(self, telegram_id: int) -> User:
        user = await self.get_user(telegram_id); user.status = UserStatus.BLOCKED
        return await self._save(user)

    async def unblock_user(self, telegram_id: int) -> User:
        user = await self.get_user(telegram_id)
        user.status = UserStatus.ACTIVE
        user.warnings = 0
        return await self._save(user)

    async def _save(self, user: User) -> User:
        updated = await self._user_repository.update(user)
        assert updated is not None
        return updated

    async def get_active_telegram_ids(self, *, registered_only: bool = False) -> list[int]:
        return await self._user_repository.list_active_telegram_ids(registered_only=registered_only)

    async def get_blocked_users_page(self, *, page: int, page_size: int) -> tuple[list[User], int, int]:
        total = await self._user_repository.count_blocked()
        total_pages = max(1, ceil(total / page_size))
        page = min(max(page, 0), total_pages - 1)
        return await self._user_repository.list_blocked_page(offset=page * page_size, limit=page_size), total, page
