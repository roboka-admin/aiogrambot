from collections.abc import Sequence

from models.admin import Admin, AdminPermission, AdminRole, AdminStatus
from repositories.interfaces.admin import IAdminRepository


class AdminService:
    """Business operations for administrator accounts and permissions."""

    def __init__(self, *, admin_repository: IAdminRepository) -> None:
        self._admin_repository = admin_repository

    async def get_admin(self, telegram_id: int) -> Admin | None:
        return await self._admin_repository.get(telegram_id)

    async def add_admin(self, telegram_id: int) -> Admin:
        existing = await self._admin_repository.get(telegram_id)
        if existing is not None:
            return existing
        return await self._admin_repository.create(Admin(telegram_id=telegram_id))

    async def ensure_owner(self, telegram_id: int) -> Admin:
        existing = await self._admin_repository.get(telegram_id)
        if existing is not None:
            return existing
        return await self._admin_repository.create(
            Admin(telegram_id=telegram_id, role=AdminRole.OWNER)
        )

    async def deactivate_admin(self, telegram_id: int) -> None:
        await self._admin_repository.set_status(telegram_id, AdminStatus.INACTIVE.value)

    async def activate_admin(self, telegram_id: int) -> None:
        await self._admin_repository.set_status(telegram_id, AdminStatus.ACTIVE.value)

    async def sync_permission_registry(
        self, permissions: Sequence[AdminPermission]
    ) -> None:
        await self._admin_repository.sync_permissions(permissions)

    async def get_permissions(self, telegram_id: int) -> set[str]:
        return await self._admin_repository.get_permissions(telegram_id)

    async def set_permissions(
        self, telegram_id: int, permission_keys: set[str]
    ) -> None:
        await self._admin_repository.set_permissions(telegram_id, permission_keys)

    async def has_permission(self, telegram_id: int, permission_key: str) -> bool:
        admin = await self._admin_repository.get(telegram_id)
        if admin is None or admin.status != AdminStatus.ACTIVE:
            return False
        if admin.role == AdminRole.OWNER:
            return True
        return await self._admin_repository.has_permission(telegram_id, permission_key)
