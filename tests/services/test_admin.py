from unittest.mock import AsyncMock, MagicMock, call

import pytest

from core.admin_permissions import ADMIN_PERMISSION_REGISTRY
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
