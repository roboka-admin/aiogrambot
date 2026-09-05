from abc import ABC, abstractmethod
from collections.abc import Sequence

from models.admin import Admin, AdminPermission


class IAdminRepository(ABC):
    @abstractmethod
    async def get(self, telegram_id: int) -> Admin | None: ...

    @abstractmethod
    async def list_admins(self) -> Sequence[Admin]: ...

    @abstractmethod
    async def create(self, admin: Admin) -> Admin: ...

    @abstractmethod
    async def delete(self, telegram_id: int) -> None: ...

    @abstractmethod
    async def set_status(self, telegram_id: int, status: str) -> None: ...

    @abstractmethod
    async def list_permissions(self) -> Sequence[AdminPermission]: ...

    @abstractmethod
    async def sync_permissions(self, permissions: Sequence[AdminPermission]) -> None: ...

    @abstractmethod
    async def get_permissions(self, telegram_id: int) -> set[str]: ...

    @abstractmethod
    async def set_permissions(self, telegram_id: int, permission_keys: set[str]) -> None: ...

    @abstractmethod
    async def has_permission(self, telegram_id: int, permission_key: str) -> bool: ...
