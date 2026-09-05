from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from core.timezone import tehran_now
from models.base import Base


class AdminRecord(Base):
    __tablename__ = "admins"

    telegram_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="admin")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=tehran_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=tehran_now, onupdate=tehran_now
    )


class AdminPermissionRecord(Base):
    __tablename__ = "admin_permissions"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)


class AdminPermissionAssignmentRecord(Base):
    __tablename__ = "admin_permission_assignments"

    admin_telegram_id: Mapped[int] = mapped_column(
        ForeignKey("admins.telegram_id", ondelete="CASCADE"), primary_key=True, autoincrement=False
    )
    permission_key: Mapped[str] = mapped_column(
        ForeignKey("admin_permissions.key", ondelete="CASCADE"), primary_key=True
    )
