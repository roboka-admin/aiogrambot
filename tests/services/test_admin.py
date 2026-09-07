from unittest.mock import AsyncMock, MagicMock, call

import pytest

from core.admin_permissions import ADMIN_PERMISSION_REGISTRY
from exceptions.user import UserNotFoundError
from models.admin import Admin, AdminRole
from services.admin import AdminService


@pytest.mark.asyncio
async def test_bootstrap_syncs_permission_registry_and_seeds_configured_owners():
    repository = MagicMock()
    repository.sync_permissions = AsyncMock()
    repository.get = AsyncMock(side_effect=[None, None])
    repository.create = AsyncMock(
        side_effect=lambda admin: admin,
    )
    user_repository = MagicMock()
    service = AdminService(admin_repository=repository, user_repository=user_repository)

    await service.bootstrap((101, 202))

    repository.sync_permissions.assert_awaited_once_with(ADMIN_PERMISSION_REGISTRY)
    assert repository.get.await_args_list == [call(101), call(202)]
    assert repository.create.await_args_list == [
        call(Admin(telegram_id=101, role=AdminRole.OWNER)),
        call(Admin(telegram_id=202, role=AdminRole.OWNER)),
    ]


@pytest.mark.asyncio
async def test_bootstrap_does_not_replace_existing_database_admin():
    existing_admin = Admin(telegram_id=101, role=AdminRole.ADMIN)
    repository = MagicMock()
    repository.sync_permissions = AsyncMock()
    repository.get = AsyncMock(return_value=existing_admin)
    repository.create = AsyncMock()
    user_repository = MagicMock()
    service = AdminService(admin_repository=repository, user_repository=user_repository)

    await service.bootstrap((101,))

    repository.sync_permissions.assert_awaited_once_with(ADMIN_PERMISSION_REGISTRY)
    repository.get.assert_awaited_once_with(101)
    repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_managed_admin_rejects_user_who_has_not_started_bot():
    admin_repository = MagicMock()
    admin_repository.get = AsyncMock(side_effect=[
        Admin(telegram_id=100, role=AdminRole.OWNER),
        Admin(telegram_id=100, role=AdminRole.OWNER),
        None,
    ])
    user_repository = MagicMock()
    user_repository.exists = AsyncMock(return_value=False)

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

    user_repository.exists.assert_awaited_once_with(200)
    admin_repository.create.assert_not_called()


@pytest.mark.asyncio
async def test_create_managed_admin_accepts_user_who_has_started_bot():
    admin_repository = MagicMock()
    admin_repository.get = AsyncMock(side_effect=[
        Admin(telegram_id=100, role=AdminRole.OWNER),
        Admin(telegram_id=100, role=AdminRole.OWNER),
        None,
    ])
    admin_repository.create = AsyncMock(return_value=Admin(telegram_id=200))
    admin_repository.set_permissions = AsyncMock()
    user_repository = MagicMock()
    user_repository.exists = AsyncMock(return_value=True)

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
    user_repository.exists.assert_awaited_once_with(200)
    admin_repository.create.assert_awaited_once()
    admin_repository.set_permissions.assert_awaited_once_with(200, {"support"})
