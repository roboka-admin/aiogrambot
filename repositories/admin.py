from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.admin import Admin, AdminPermission, AdminRole, AdminStatus
from models.admin_db import (
    AdminPermissionAssignmentRecord,
    AdminPermissionRecord,
    AdminRecord,
)
from repositories.interfaces.admin import IAdminRepository


class AdminRepository(IAdminRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, telegram_id: int) -> Admin | None:
        result = await self._session.execute(
            select(AdminRecord).where(AdminRecord.telegram_id == telegram_id)
        )
        record = result.scalar_one_or_none()
        return self._to_domain(record) if record else None

    async def create(self, admin: Admin) -> Admin:
        record = AdminRecord(
            telegram_id=admin.telegram_id,
            role=admin.role.value,
            status=admin.status.value,
            created_at=admin.created_at,
            updated_at=admin.updated_at,
        )
        self._session.add(record)
        await self._session.flush()
        return self._to_domain(record)

    async def set_status(self, telegram_id: int, status: str) -> None:
        record = await self._get_record(telegram_id)
        if record is not None:
            record.status = status
            await self._session.flush()

    async def list_permissions(self) -> Sequence[AdminPermission]:
        result = await self._session.execute(
            select(AdminPermissionRecord).order_by(AdminPermissionRecord.key)
        )
        return [self._permission_to_domain(record) for record in result.scalars()]

    async def sync_permissions(self, permissions: Sequence[AdminPermission]) -> None:
        if not permissions:
            return
        values = [
            {
                "key": permission.key,
                "title": permission.title,
                "description": permission.description,
            }
            for permission in permissions
        ]
        statement = insert(AdminPermissionRecord).values(values)
        statement = statement.on_duplicate_key_update(
            title=statement.inserted.title,
            description=statement.inserted.description,
        )
        await self._session.execute(statement)

    async def get_permissions(self, telegram_id: int) -> set[str]:
        result = await self._session.execute(
            select(AdminPermissionAssignmentRecord.permission_key).where(
                AdminPermissionAssignmentRecord.admin_telegram_id == telegram_id
            )
        )
        return set(result.scalars())

    async def set_permissions(self, telegram_id: int, permission_keys: set[str]) -> None:
        await self._session.execute(
            delete(AdminPermissionAssignmentRecord).where(
                AdminPermissionAssignmentRecord.admin_telegram_id == telegram_id
            )
        )
        if permission_keys:
            self._session.add_all(
                AdminPermissionAssignmentRecord(
                    admin_telegram_id=telegram_id,
                    permission_key=permission_key,
                )
                for permission_key in permission_keys
            )
        await self._session.flush()

    async def has_permission(self, telegram_id: int, permission_key: str) -> bool:
        result = await self._session.execute(
            select(AdminPermissionAssignmentRecord.admin_telegram_id).where(
                AdminPermissionAssignmentRecord.admin_telegram_id == telegram_id,
                AdminPermissionAssignmentRecord.permission_key == permission_key,
            )
        )
        return result.scalar_one_or_none() is not None

    async def _get_record(self, telegram_id: int) -> AdminRecord | None:
        result = await self._session.execute(
            select(AdminRecord).where(AdminRecord.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _to_domain(record: AdminRecord) -> Admin:
        return Admin(
            telegram_id=record.telegram_id,
            role=AdminRole(record.role),
            status=AdminStatus(record.status),
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _permission_to_domain(record: AdminPermissionRecord) -> AdminPermission:
        return AdminPermission(
            key=record.key,
            title=record.title,
            description=record.description,
        )
