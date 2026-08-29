from models.user import RegistrationStatus, User, UserStatus
from services.user import UserService


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[int, User] = {}

    async def exists(self, telegram_id: int) -> bool:
        return telegram_id in self.users

    async def create(self, user: User) -> User:
        self.users[user.telegram_id] = user
        return user

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return self.users.get(telegram_id)

    async def update(self, user: User) -> User | None:
        if user.telegram_id not in self.users:
            return None
        self.users[user.telegram_id] = user
        return user

    async def delete(self, telegram_id: int) -> bool:
        return self.users.pop(telegram_id, None) is not None

    async def list_all(self) -> list[User]:
        return list(self.users.values())

    async def list_page(self, *, offset: int, limit: int) -> list[User]:
        users = list(self.users.values())
        return users[offset : offset + limit]

    async def count(self) -> int:
        return len(self.users)

    async def count_registered(self) -> int:
        return sum(
            user.registration_status == RegistrationStatus.REGISTERED
            for user in self.users.values()
        )

    async def count_unregistered(self) -> int:
        return sum(
            user.registration_status == RegistrationStatus.UNREGISTERED
            for user in self.users.values()
        )

    async def list_active_telegram_ids(self, *, registered_only: bool = False) -> list[int]:
        return [
            user.telegram_id
            for user in self.users.values()
            if user.status == UserStatus.ACTIVE
            and (not registered_only or user.registration_status == RegistrationStatus.REGISTERED)
        ]

    async def list_blocked_page(self, *, offset: int, limit: int) -> list[User]:
        users = [user for user in self.users.values() if user.status == UserStatus.BLOCKED]
        return users[offset : offset + limit]

    async def count_blocked(self) -> int:
        return sum(user.status == UserStatus.BLOCKED for user in self.users.values())

    async def count_active(self) -> int:
        return sum(user.status == UserStatus.ACTIVE for user in self.users.values())

    async def count_active_today(self, today_start) -> int:
        return sum(
            user.last_seen_at is not None and user.last_seen_at >= today_start
            for user in self.users.values()
        )

    async def count_active_last_7_days(self, seven_days_ago) -> int:
        return sum(
            user.last_seen_at is not None and user.last_seen_at >= seven_days_ago
            for user in self.users.values()
        )

    async def count_inactive_30_days(self, thirty_days_ago) -> int:
        return sum(
            user.last_seen_at is None or user.last_seen_at < thirty_days_ago
            for user in self.users.values()
        )


def make_service() -> tuple[UserService, FakeUserRepository]:
    repository = FakeUserRepository()
    return UserService(user_repository=repository), repository


def make_user(telegram_id: int = 123) -> User:
    return User(telegram_id=telegram_id, telegram_name="Test User")


def test_get_or_create_tracks_unregistered_user():
    import asyncio

    async def scenario() -> None:
        service, repository = make_service()

        user = await service.get_or_create_telegram_user(
            telegram_id=123,
            telegram_name="Test User",
            username="tester",
        )

        assert user.telegram_id == 123
        assert user.registration_status == RegistrationStatus.UNREGISTERED
        assert await repository.exists(123)

    asyncio.run(scenario())


def test_registration_changes_status_and_profile():
    import asyncio

    async def scenario() -> None:
        service, repository = make_service()
        await repository.create(make_user())

        user = await service.complete_registration(
            telegram_id=123,
            name=" Ali ",
            age=28,
        )

        assert user.name == "Ali"
        assert user.age == 28
        assert user.registration_status == RegistrationStatus.REGISTERED

    asyncio.run(scenario())


def test_add_and_remove_coins_validate_amount():
    import asyncio

    async def scenario() -> None:
        service, repository = make_service()
        await repository.create(make_user())

        user = await service.add_coins(123, 10)
        assert user.coins == 10

        user = await service.remove_coins(123, 3)
        assert user.coins == 7

        user = await service.remove_coins(123, 100)
        assert user.coins == 0

        for method in (service.add_coins, service.remove_coins):
            try:
                await method(123, 0)
            except ValueError:
                pass
            else:
                raise AssertionError("Expected ValueError for zero amount")

    asyncio.run(scenario())


def test_third_warning_blocks_user():
    import asyncio

    async def scenario() -> None:
        service, repository = make_service()
        await repository.create(make_user())

        await service.add_warning(123)
        await service.add_warning(123)
        user = await service.add_warning(123)

        assert user.warnings == 3
        assert user.status == UserStatus.BLOCKED

    asyncio.run(scenario())


def test_unblock_resets_warnings():
    import asyncio

    async def scenario() -> None:
        service, repository = make_service()
        await repository.create(make_user())
        await service.block_user(123)
        await service.add_warning(123)

        user = await service.unblock_user(123)

        assert user.status == UserStatus.ACTIVE
        assert user.warnings == 0

    asyncio.run(scenario())
