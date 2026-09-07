from collections.abc import Iterable, Sequence

from core.admin_permissions import ADMIN_PERMISSION_REGISTRY
from core.transaction import NullTransactionManager, TransactionManager, transactional
from models.admin import Admin, AdminPermission, AdminRole, AdminStatus
from repositories.interfaces.admin import IAdminRepository


class AdminService:
    """Business operations for administrator accounts and permissions."""

    def __init__(
        self,
        *,
        admin_repository: IAdminRepository,
        transaction_manager: TransactionManager | None = None,
    ) -> None:
        self._admin_repository = admin_repository
        self._transaction_manager = transaction_manager or NullTransactionManager()

    @transactional
    async def bootstrap(self, owner_telegram_ids: Iterable[int]) -> None:
        """Initialize configured owners and the permission registry at application startup."""
        await self.sync_permission_registry(ADMIN_PERMISSION_REGISTRY)
        for telegram_id in owner_telegram_ids:
            await self.ensure_owner(telegram_id)

    @transactional
    async def get_admin(self, telegram_id: int) -> Admin | None:
        return await self._admin_repository.get(telegram_id)

    @transactional
    async def list_admins(self) -> Sequence[Admin]:
        return await self._admin_repository.list_admins()

    @transactional
    async def is_active_admin(self, telegram_id: int) -> bool:
        admin = await self._admin_repository.get(telegram_id)
        return admin is not None and admin.status is AdminStatus.ACTIVE

    @transactional
    async def add_admin(self, telegram_id: int) -> Admin:
        existing = await self._admin_repository.get(telegram_id)
        if existing is not None:
            return existing
        return await self._admin_repository.create(Admin(telegram_id=telegram_id))

    @transactional
    async def create_managed_admin(
        self,
        *,
        actor_telegram_id: int,
        telegram_id: int,
        permission_keys: set[str],
    ) -> Admin:
        await self._ensure_can_manage(actor_telegram_id)
        await self._validate_assignable_permissions(actor_telegram_id, permission_keys)

        if await self._admin_repository.get(telegram_id) is not None:
            raise ValueError("admin already exists")

        admin = await self._admin_repository.create(Admin(telegram_id=telegram_id))
        await self._admin_repository.set_permissions(telegram_id, permission_keys)
        return admin

    @transactional
    async def deactivate_managed_admin(
        self, *, actor_telegram_id: int, telegram_id: int
    ) -> bool:
        await self._ensure_can_manage(actor_telegram_id)
        target = await self._admin_repository.get(telegram_id)
        if target is None or target.role is AdminRole.OWNER:
            return False
        if target.telegram_id == actor_telegram_id:
            return False
        await self._admin_repository.set_status(telegram_id, AdminStatus.INACTIVE.value)
        return True

    @transactional
    async def activate_managed_admin(
        self, *, actor_telegram_id: int, telegram_id: int
    ) -> bool:
        await self._ensure_can_manage(actor_telegram_id)
        target = await self._admin_repository.get(telegram_id)
        if target is None or target.role is AdminRole.OWNER:
            return False
        await self._admin_repository.set_status(telegram_id, AdminStatus.ACTIVE.value)
        return True

    @transactional
    async def remove_managed_admin(
        self, *, actor_telegram_id: int, telegram_id: int
    ) -> bool:
        await self._ensure_can_manage(actor_telegram_id)
        target = await self._admin_repository.get(telegram_id)
        if target is None or target.role is AdminRole.OWNER:
            return False
        if target.telegram_id == actor_telegram_id:
            return False
        await self._admin_repository.delete(telegram_id)
        return True

    @transactional
    async def set_managed_admin_permissions(
        self,
        *,
        actor_telegram_id: int,
        telegram_id: int,
        permission_keys: set[str],
    ) -> bool:
        await self._ensure_can_manage(actor_telegram_id)
        target = await self._admin_repository.get(telegram_id)
        if target is None or target.role is AdminRole.OWNER:
            return False
        await self._validate_assignable_permissions(actor_telegram_id, permission_keys)
        await self._admin_repository.set_permissions(telegram_id, permission_keys)
        return True

    @transactional
    async def ensure_owner(self, telegram_id: int) -> Admin:
        existing = await self._admin_repository.get(telegram_id)
        if existing is not None:
            return existing
        return await self._admin_repository.create(
            Admin(telegram_id=telegram_id, role=AdminRole.OWNER)
        )

    @transactional
    async def deactivate_admin(self, telegram_id: int) -> None:
        await self._admin_repository.set_status(telegram_id, AdminStatus.INACTIVE.value)

    @transactional
    async def activate_admin(self, telegram_id: int) -> None:
        await self._admin_repository.set_status(telegram_id, AdminStatus.ACTIVE.value)

    @transactional
    async def sync_permission_registry(
        self, permissions: Sequence[AdminPermission]
    ) -> None:
        await self._admin_repository.sync_permissions(permissions)

    @transactional
    async def get_permissions(self, telegram_id: int) -> set[str]:
        return await self._admin_repository.get_permissions(telegram_id)

    @transactional
    async def get_effective_permissions(self, telegram_id: int) -> set[str]:
        """Return the capabilities an active administrator can actually use."""
        admin = await self._admin_repository.get(telegram_id)
        if admin is None or admin.status is not AdminStatus.ACTIVE:
            return set()
        if admin.role is AdminRole.OWNER:
            return {permission.key for permission in ADMIN_PERMISSION_REGISTRY}
        return await self._admin_repository.get_permissions(telegram_id)

    @transactional
    async def set_permissions(
        self, telegram_id: int, permission_keys: set[str]
    ) -> None:
        await self._admin_repository.set_permissions(telegram_id, permission_keys)

    @transactional
    async def has_permission(self, telegram_id: int, permission_key: str) -> bool:
        admin = await self._admin_repository.get(telegram_id)
        if admin is None or admin.status != AdminStatus.ACTIVE:
            return False
        if admin.role == AdminRole.OWNER:
            return True
        return await self._admin_repository.has_permission(telegram_id, permission_key)

    async def _ensure_can_manage(self, actor_telegram_id: int) -> None:
        if not await self.has_permission(actor_telegram_id, "admins"):
            raise PermissionError("admin management permission required")

    async def _validate_assignable_permissions(
        self, actor_telegram_id: int, permission_keys: set[str]
    ) -> None:
        known_permissions = {permission.key for permission in ADMIN_PERMISSION_REGISTRY}
        unknown = permission_keys - known_permissions
        if unknown:
            raise ValueError(f"unknown permission keys: {sorted(unknown)}")

        actor_permissions = await self.get_effective_permissions(actor_telegram_id)
        if not permission_keys.issubset(actor_permissions):
            raise PermissionError("cannot assign permissions the actor does not have")
