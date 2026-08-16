from typing import Protocol

from models.user import User


class IUserRepository(Protocol):
    """
    Abstraction for the user data access required by services.

    Services depend on this interface, not on a concrete repository
    implementation.
    """

    async def exists(self, telegram_id: int) -> bool:
        """Check whether a user exists."""
        ...

    async def create(self, user: User) -> User:
        """Store a new user."""
        ...
