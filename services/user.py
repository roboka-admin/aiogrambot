from exceptions.user import UserNotFoundError
from models.user import User
from repositories.interfaces.user import IUserRepository


class UserService:
    """Handles general user-related business operations."""

    def __init__(
        self,
        *,
        user_repository: IUserRepository,
    ) -> None:
        self._user_repository = user_repository

    async def exists(self, telegram_id: int) -> bool:
        """Check whether a Telegram user is registered."""
        return await self._user_repository.exists(telegram_id)

    async def get_user(self, telegram_id: int) -> User:
        """Return a registered user or raise if the user does not exist."""
        user = await self._user_repository.get_by_telegram_id(telegram_id)

        if user is None:
            raise UserNotFoundError()

        return user
