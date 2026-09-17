"""Compact, structured view of bot health for one monitoring window."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from core.log_buffer import LogIssue


@dataclass(frozen=True, slots=True)
class ResourceMetrics:
    cpu_percent: float | None
    memory_percent: float | None
    memory_used_mb: int | None
    memory_total_mb: int | None
    disk_percent: float | None
    disk_used_gb: float | None
    disk_total_gb: float | None


@dataclass(frozen=True, slots=True)
class DatabaseMetrics:
    healthy: bool
    latency_ms: float | None
    size_mb: float | None
    row_count: int | None


@dataclass(frozen=True, slots=True)
class ActivityMetrics:
    """Counts inside the window (``since`` .. ``now``)."""

    updates: int
    errors: int
    spam_warnings: int
    spam_blocks: int
    admin_blocks_total: int
    bot_blocked_by_users: int
    bot_blocked_by_users_total: int


@dataclass(frozen=True, slots=True)
class MonitoringSnapshot:
    taken_at: datetime
    window_start: datetime
    window_seconds: int
    uptime_seconds: int
    resources: ResourceMetrics
    database: DatabaseMetrics
    activity: ActivityMetrics
    issues: tuple[LogIssue, ...] = field(default_factory=tuple)
