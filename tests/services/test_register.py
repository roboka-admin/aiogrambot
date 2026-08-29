import asyncio

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


def test_register_completes_registration():
    async def scenario() -> None:
        repository = FakeUserRepository()
        repository.users[123] = User(telegram_id=123, telegram_name="Telegram User")
        service = RegisterService(user_repository=repository)

        user = await service.register(telegram_id=123, name=" Ali ", age=28)

        assert user.name == "Ali"
        assert user.age == 28
        assert user.registration_status == RegistrationStatus.REGISTERED

    asyncio.run(scenario())


def test_register_rejects_already_registered_user():
    async def scenario() -> None:
        repository = FakeUserRepository()
        repository.users[123] = User(
            telegram_id=123,
            telegram_name="Telegram User",
            registration_status=RegistrationStatus.REGISTERED,
        )
        service = RegisterService(user_repository=repository)

        try:
            await service.register(telegram_id=123, name="Ali", age=28)
        except UserAlreadyExistsError:
            return
        raise AssertionError("Expected UserAlreadyExistsError")

    asyncio.run(scenario())


def test_register_requires_tracked_user():
    async def scenario() -> None:
        service = RegisterService(user_repository=FakeUserRepository())

        try:
            await service.register(telegram_id=999, name="Ali", age=28)
        except RuntimeError:
            return
        raise AssertionError("Expected RuntimeError")

    asyncio.run(scenario())
