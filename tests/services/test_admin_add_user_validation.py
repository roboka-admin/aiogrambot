from unittest.mock import AsyncMock, MagicMock

import pytest

from exceptions.user import UserNotFoundError
from models.admin import Admin, AdminRole
from models.user import User
from services.admin import AdminService


@pytest.mark.asyncio
async def test_create_managed_admin_rejects_user_who_has_not_started_bot():
    admin_repository = MagicMock()
    admin_repository.get = AsyncMock(side_effect=[
        Admin(telegram_id=100, role=AdminRole.OWNER),
        None,
    ])
    user_repository = MagicMock()
    user_repository.get_by_telegram_id = AsyncMock(return_value=None)

    service = AdminService(
        admin_repository=admin_repository,
        user_repository=user_repository,
    )

    with pytest.raises(UserNotFoundError):
        await service.create_managed_admin(
            actor_telegram_id=100,
            telegram_id=200,
            permission_keys=set(),
        )

    user_repository.get_by_telegram_id.assert_awaited_once_with(200)
    admin_repository.create.assert_not_called()


@pytest.mark.asyncio
async def test_create_managed_admin_accepts_user_who_has_started_bot():
    target_user = User(telegram_id=200, telegram_name="Target")
    admin_repository = MagicMock()
    admin_repository.get = AsyncMock(side_effect=[
        Admin(telegram_id=100, role=AdminRole.OWNER),
        None,
    ])
    admin_repository.create = AsyncMock(return_value=Admin(telegram_id=200))
    admin_repository.set_permissions = AsyncMock()
    user_repository = MagicMock()
    user_repository.get_by_telegram_id = AsyncMock(return_value=target_user)

    service = AdminService(
        admin_repository=admin_repository,
        user_repository=user_repository,
    )

    admin = await service.create_managed_admin(
        actor_telegram_id=100,
        telegram_id=200,
        permission_keys={"support"},
    )

    assert admin.telegram_id == 200
    user_repository.get_by_telegram_id.assert_awaited_once_with(200)
    admin_repository.create.assert_awaited_once()
    admin_repository.set_permissions.assert_awaited_once_with(200, {"support"})
