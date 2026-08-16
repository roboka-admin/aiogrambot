from models.user import User
from repositories.interfaces.user import IUserRepository
from exceptions.user import UserAlreadyExistsError


class RegisterService:
    """
    Handles user registration business logic.
    """

    def __init__(
        self,
        *,
        user_repository: IUserRepository,
    ) -> None:
        self._user_repository = user_repository

    async def register(
        self,
        *,
        telegram_id: int,
        name: str,
        age: int,
    ) -> User:
        """
        Register a new Telegram user.

        Raises:
            UserAlreadyExistsError:
                If the user is already registered.
        """

        if await self._user_repository.exists(telegram_id):
            raise UserAlreadyExistsError

        user = User(
            telegram_id=telegram_id,
            name=name,
            age=age,
        )

        return await self._user_repository.create(user)
