from datetime import timedelta

import pytest

from core.timezone import tehran_now
from exceptions.user import UserNotFoundError
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
            and (
                not registered_only
                or user.registration_status == RegistrationStatus.REGISTERED
            )
        ]

    async def list_blocked_page(self, *, offset: int, limit: int) -> list[User]:
        users = [
            user for user in self.users.values() if user.status == UserStatus.BLOCKED
        ]
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


@pytest.fixture
def service_and_repository() -> tuple[UserService, FakeUserRepository]:
    repository = FakeUserRepository()
    return UserService(user_repository=repository), repository


def make_user(telegram_id: int = 123) -> User:
    return User(telegram_id=telegram_id, telegram_name="Test User")


@pytest.mark.asyncio
async def test_get_or_create_tracks_unregistered_user(service_and_repository):
    service, repository = service_and_repository
    user = await service.get_or_create_telegram_user(
        telegram_id=123,
        telegram_name="Test User",
        username="tester",
    )
    assert user.telegram_id == 123
    assert user.registration_status == RegistrationStatus.UNREGISTERED
    assert await repository.exists(123)


@pytest.mark.asyncio
async def test_get_or_create_updates_existing_identity(service_and_repository):
    service, repository = service_and_repository
    user = make_user()
    old_seen = user.last_seen_at
    await repository.create(user)

    updated = await service.get_or_create_telegram_user(
        telegram_id=123,
        telegram_name="Renamed",
        username="new_username",
    )

    assert updated.telegram_name == "Renamed"
    assert updated.username == "new_username"
    assert updated.last_seen_at >= old_seen


@pytest.mark.asyncio
async def test_get_user_raises_for_unknown_user(service_and_repository):
    service, _ = service_and_repository
    with pytest.raises(UserNotFoundError):
        await service.get_user(999)


@pytest.mark.asyncio
async def test_registration_changes_status_and_profile(service_and_repository):
    service, repository = service_and_repository
    await repository.create(make_user())
    user = await service.complete_registration(
        telegram_id=123,
        name=" Ali ",
        age=28,
    )
    assert user.name == "Ali"
    assert user.age == 28
    assert user.registration_status == RegistrationStatus.REGISTERED


@pytest.mark.asyncio
async def test_complete_registration_rejects_registered_user(service_and_repository):
    service, repository = service_and_repository
    user = make_user()
    user.registration_status = RegistrationStatus.REGISTERED
    await repository.create(user)

    with pytest.raises(ValueError):
        await service.complete_registration(telegram_id=123, name="Ali", age=28)


@pytest.mark.asyncio
async def test_update_name_and_age(service_and_repository):
    service, repository = service_and_repository
    await repository.create(make_user())

    user = await service.update_name(123, "  Saeed  ")
    assert user.name == "Saeed"
    user = await service.update_age(123, 30)
    assert user.age == 30


@pytest.mark.asyncio
async def test_add_and_remove_coins_validate_amount(service_and_repository):
    service, repository = service_and_repository
    await repository.create(make_user())
    user = await service.add_coins(123, 10)
    assert user.coins == 10
    user = await service.remove_coins(123, 3)
    assert user.coins == 7
    user = await service.remove_coins(123, 100)
    assert user.coins == 0
    for method in (service.add_coins, service.remove_coins):
        with pytest.raises(ValueError):
            await method(123, 0)


@pytest.mark.asyncio
async def test_third_warning_blocks_user(service_and_repository):
    service, repository = service_and_repository
    await repository.create(make_user())
    await service.add_warning(123)
    await service.add_warning(123)
    user = await service.add_warning(123)
    assert user.warnings == 3
    assert user.status == UserStatus.BLOCKED


@pytest.mark.asyncio
async def test_unblock_resets_warnings(service_and_repository):
    service, repository = service_and_repository
    await repository.create(make_user())
    await service.block_user(123)
    await service.add_warning(123)
    user = await service.unblock_user(123)
    assert user.status == UserStatus.ACTIVE
    assert user.warnings == 0


@pytest.mark.asyncio
async def test_user_counts_and_active_recipient_filter(service_and_repository):
    service, repository = service_and_repository
    registered = make_user(1)
    registered.registration_status = RegistrationStatus.REGISTERED
    unregistered = make_user(2)
    blocked = make_user(3)
    blocked.status = UserStatus.BLOCKED
    await repository.create(registered)
    await repository.create(unregistered)
    await repository.create(blocked)

    counts = await service.get_user_counts()
    assert counts == {"total": 3, "registered": 1, "unregistered": 2, "blocked": 1}
    assert await service.get_active_telegram_ids() == [1, 2]
    assert await service.get_active_telegram_ids(registered_only=True) == [1]


@pytest.mark.asyncio
async def test_user_statistics_and_pagination(service_and_repository):
    service, repository = service_and_repository
    now = tehran_now()
    recent = make_user(1)
    recent.last_seen_at = now
    old = make_user(2)
    old.last_seen_at = now - timedelta(days=40)
    blocked = make_user(3)
    blocked.status = UserStatus.BLOCKED
    await repository.create(recent)
    await repository.create(old)
    await repository.create(blocked)

    users, total, page = await service.get_users_page(page=99, page_size=2)
    assert total == 3
    assert page == 1
    assert [user.telegram_id for user in users] == [3]

    stats = await service.get_user_statistics()
    assert stats["total"] == 3
    assert stats["active_today"] >= 1
    assert stats["active_7d"] >= 1
    assert stats["inactive_30d"] == 1


@pytest.mark.asyncio
async def test_blocked_users_page_clamps_page(service_and_repository):
    service, repository = service_and_repository
    for telegram_id in (1, 2, 3):
        user = make_user(telegram_id)
        user.status = UserStatus.BLOCKED
        await repository.create(user)

    users, total, page = await service.get_blocked_users_page(page=10, page_size=2)
    assert total == 3
    assert page == 1
    assert [user.telegram_id for user in users] == [3]
