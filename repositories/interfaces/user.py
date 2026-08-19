from typing import Protocol

from models.user import User


class IUserRepository(Protocol):
    """Abstraction for user persistence."""

    async def exists(self, telegram_id: int) -> bool:
        ...

    async def create(self, user: User) -> User:
        ...

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        ...

    async def update(self, user: User) -> User | None:
        ...

    async def delete(self, telegram_id: int) -> bool:
        ...

    async def list_all(self) -> list[User]:
        ...

    async def list_page(self, *, offset: int, limit: int) -> list[User]:
        ...

    async def count(self) -> int:
        ...
