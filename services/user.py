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
