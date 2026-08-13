from models.user import User


class UserRepository:
    """
    Repository responsible for storing and retrieving User objects.

    Current implementation uses in-memory storage.
    It can later be replaced with SQLAlchemy without changing services.
    """

    def __init__(self) -> None:
        self._users: dict[int, User] = {}

    async def create(self, user: User) -> User:
        """
        Store a new user.
        """
        self._users[user.telegram_id] = user
        return user

    async def exists(self, telegram_id: int) -> bool:
        """
        Check whether a user already exists.
        """
        return telegram_id in self._users

    async def get_by_telegram_id(
        self,
        telegram_id: int,
    ) -> User | None:
        """
        Retrieve a user by Telegram ID.
        """
        return self._users.get(telegram_id)

    async def update(self, user: User) -> User:
        """
        Replace an existing user.
        """
        self._users[user.telegram_id] = user
        return user

    async def delete(self, telegram_id: int) -> bool:
        """
        Delete a user.

        Returns:
            True if the user existed and was deleted.
            False otherwise.
        """
        return self._users.pop(telegram_id, None) is not None

    async def list_all(self) -> list[User]:
        """
        Return all users.
        """
        return list(self._users.values())