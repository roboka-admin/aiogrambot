import pytest

from exceptions.user import UserAlreadyExistsError
from models.user import RegistrationStatus, User
from services.register import RegisterService


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[int, User] = {}

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return self.users.get(telegram_id)

    async def update(self, user: User) -> User | None:
        if user.telegram_id not in self.users:
            return None
        self.users[user.telegram_id] = user
        return user


@pytest.mark.asyncio
async def test_register_completes_registration():
    repository = FakeUserRepository()
    repository.users[123] = User(telegram_id=123, telegram_name="Telegram User")
    service = RegisterService(user_repository=repository)
    user = await service.register(telegram_id=123, name=" Ali ", age=28)
    assert user.name == "Ali"
    assert user.age == 28
    assert user.registration_status == RegistrationStatus.REGISTERED


@pytest.mark.asyncio
async def test_register_rejects_already_registered_user():
    repository = FakeUserRepository()
    repository.users[123] = User(
        telegram_id=123,
        telegram_name="Telegram User",
        registration_status=RegistrationStatus.REGISTERED,
    )
    service = RegisterService(user_repository=repository)
    with pytest.raises(UserAlreadyExistsError):
        await service.register(telegram_id=123, name="Ali", age=28)


@pytest.mark.asyncio
async def test_register_requires_tracked_user():
    service = RegisterService(user_repository=FakeUserRepository())
    with pytest.raises(RuntimeError):
        await service.register(telegram_id=999, name="Ali", age=28)
