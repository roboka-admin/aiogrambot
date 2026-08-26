from exceptions.user import UserAlreadyExistsError
from models.user import RegistrationStatus, User
from repositories.interfaces.user import IUserRepository


class RegisterService:
    """Completes registration for an already tracked Telegram user."""

    def __init__(self, *, user_repository: IUserRepository) -> None:
        self._user_repository = user_repository

    async def register(self, *, telegram_id: int, name: str, age: int) -> User:
        user = await self._user_repository.get_by_telegram_id(telegram_id)
        if user is None:
            raise RuntimeError("Telegram user must be tracked before registration")
        if user.registration_status == RegistrationStatus.REGISTERED:
            raise UserAlreadyExistsError
        user.name = name.strip()
        user.age = age
        user.registration_status = RegistrationStatus.REGISTERED
        updated = await self._user_repository.update(user)
        assert updated is not None
        return updated
