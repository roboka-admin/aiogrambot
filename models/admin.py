from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AdminStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class AdminRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class Admin:
    telegram_id: int
    role: AdminRole = AdminRole.ADMIN
    status: AdminStatus = AdminStatus.ACTIVE
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AdminPermission:
    key: str
    title: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class AdminPermissionAssignment:
    admin_telegram_id: int
    permission_key: str
