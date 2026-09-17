"""Periodic health check: snapshot → rules → admin alerts.

Runs as a background task next to polling, outside any Telegram update, so
it opens its own short-lived repository scope per cycle (same pattern as
``BroadcastService``). Alerting policy:

- an anomaly notifies admins the first time it fires and again only after
  ``alert_cooldown`` while it keeps firing (no five-minute spam);
- when a previously reported anomaly clears, admins get one "resolved" note;
- alerts are best-effort: a failed delivery is logged, never raised.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta

from core.log_buffer import ErrorLogBuffer
from core.timezone import tehran_now
from models.antispam import AntiSpamEventType
from repositories.interfaces.antispam import IAntiSpamRepository
from repositories.interfaces.user import IUserRepository
from services.monitoring.rules import DEFAULT_THRESHOLDS, Anomaly, Severity, Thresholds, evaluate
from services.monitoring.snapshot import (
    ActivityMetrics,
    DatabaseMetrics,
    MonitoringSnapshot,
    ResourceMetrics,
)
from services.system import SystemService
from services.telegram import TelegramGateway, TelegramGatewayError

logger = logging.getLogger(__name__)

MonitoringRepositoryFactory = Callable[
    [], AbstractAsyncContextManager[tuple[IUserRepository, IAntiSpamRepository]]
]
AdminIdsProvider = Callable[[], Awaitable[Sequence[int]]]

_SEVERITY_ICON = {Severity.WARNING: "⚠️", Severity.CRITICAL: "🚨"}


class MonitoringService:
    def __init__(
        self,
        *,
        system_service: SystemService,
        log_buffer: ErrorLogBuffer,
        telegram_gateway: TelegramGateway,
        repository_factory: MonitoringRepositoryFactory,
        admin_ids_provider: AdminIdsProvider,
        thresholds: Thresholds = DEFAULT_THRESHOLDS,
        alert_cooldown: timedelta = timedelta(hours=1),
    ) -> None:
        self._system_service = system_service
        self._log_buffer = log_buffer
        self._telegram_gateway = telegram_gateway
        self._repository_factory = repository_factory
        self._admin_ids_provider = admin_ids_provider
        self._thresholds = thresholds
        self._alert_cooldown = alert_cooldown

        self._last_cycle_at: datetime | None = None
        self._last_updates_total = 0
        self._last_errors_total = 0
        # anomaly key -> (when admins were last told, human title for "resolved")
        self._active_alerts: dict[str, tuple[datetime, str]] = {}
        self._last_snapshot: MonitoringSnapshot | None = None
        self._last_anomalies: tuple[Anomaly, ...] = ()

    # ------------------------------------------------------------------ public

    @property
    def last_snapshot(self) -> MonitoringSnapshot | None:
        return self._last_snapshot

    @property
    def last_anomalies(self) -> tuple[Anomaly, ...]:
        return self._last_anomalies

    async def run_cycle(self) -> tuple[MonitoringSnapshot, list[Anomaly]]:
        """Collect one snapshot, evaluate rules, notify admins; never raises."""
        snapshot = await self.collect_snapshot()
        anomalies = evaluate(snapshot, self._thresholds)
        self._last_snapshot = snapshot
        self._last_anomalies = tuple(anomalies)

        try:
            await self._notify(snapshot, anomalies)
        except Exception:
            logger.exception("Monitoring alert delivery failed")
        return snapshot, anomalies

    async def collect_snapshot(self) -> MonitoringSnapshot:
        now = tehran_now()
        window_start = self._last_cycle_at or (now - timedelta(minutes=5))
        stats = await self._system_service.get_system_statistics()

        updates_in_window = max(0, stats.total_updates - self._last_updates_total)
        errors_in_window = max(0, stats.total_errors - self._last_errors_total)
        self._last_updates_total = stats.total_updates
        self._last_errors_total = stats.total_errors
        self._last_cycle_at = now

        spam_warnings = spam_blocks = admin_blocks_total = 0
        bot_blocked = bot_blocked_total = 0
        try:
            async with self._repository_factory() as (user_repository, antispam_repository):
                spam_warnings = await antispam_repository.count_since(
                    window_start, AntiSpamEventType.WARNING
                )
                spam_blocks = await antispam_repository.count_since(
                    window_start, AntiSpamEventType.BLOCK
                )
                admin_blocks_total = await user_repository.count_blocked()
                bot_blocked = await user_repository.count_bot_blocked_since(window_start)
                bot_blocked_total = await user_repository.count_bot_blocked()
        except Exception:
            # The DB rule will already flag this via stats.database_healthy.
            logger.exception("Monitoring could not read activity counters")

        return MonitoringSnapshot(
            taken_at=now,
            window_start=window_start,
            window_seconds=int((now - window_start).total_seconds()),
            uptime_seconds=stats.uptime_seconds,
            resources=ResourceMetrics(
                cpu_percent=stats.cpu_percent,
                memory_percent=stats.memory_percent,
                memory_used_mb=stats.memory_used_mb,
                memory_total_mb=stats.memory_total_mb,
                disk_percent=stats.disk_percent,
                disk_used_gb=stats.disk_used_gb,
                disk_total_gb=stats.disk_total_gb,
            ),
            database=DatabaseMetrics(
                healthy=stats.database_healthy,
                latency_ms=stats.db_latency_ms,
                size_mb=stats.db_size_mb,
                row_count=stats.db_row_count,
            ),
            activity=ActivityMetrics(
                updates=updates_in_window,
                errors=errors_in_window,
                spam_warnings=spam_warnings,
                spam_blocks=spam_blocks,
                admin_blocks_total=admin_blocks_total,
                bot_blocked_by_users=bot_blocked,
                bot_blocked_by_users_total=bot_blocked_total,
            ),
            issues=tuple(self._log_buffer.issues_since(window_start)[:5]),
        )

    # ----------------------------------------------------------------- alerts

    async def _notify(self, snapshot: MonitoringSnapshot, anomalies: list[Anomaly]) -> None:
        now = snapshot.taken_at
        current_keys = {anomaly.key for anomaly in anomalies}

        to_report = [
            anomaly
            for anomaly in anomalies
            if anomaly.key not in self._active_alerts
            or now - self._active_alerts[anomaly.key][0] >= self._alert_cooldown
        ]
        resolved = [
            title for key, (_, title) in self._active_alerts.items() if key not in current_keys
        ]

        for key in [key for key in self._active_alerts if key not in current_keys]:
            del self._active_alerts[key]
        for anomaly in to_report:
            self._active_alerts[anomaly.key] = (now, anomaly.title)

        if not to_report and not resolved:
            return

        text = _format_alert(snapshot, to_report, resolved)
        for admin_id in await self._admin_ids_provider():
            try:
                await self._telegram_gateway.send_message(admin_id, text)
            except TelegramGatewayError as exc:
                logger.warning("Could not deliver monitoring alert to admin %s: %s", admin_id, exc)


def _format_alert(
    snapshot: MonitoringSnapshot, anomalies: list[Anomaly], resolved: list[str]
) -> str:
    lines: list[str] = ["🩺 مانیتور سلامت ربات", ""]

    if anomalies:
        for anomaly in anomalies:
            icon = _SEVERITY_ICON[anomaly.severity]
            lines.append(f"{icon} {anomaly.title}")
            if anomaly.detail:
                lines.append(f"    {anomaly.detail}")
        lines.append("")

    if resolved:
        lines.append("✅ برطرف شد: " + "، ".join(resolved))
        lines.append("")

    if snapshot.issues and anomalies:
        lines.append("🧾 خطاهای اخیر:")
        for issue in snapshot.issues[:3]:
            lines.append(f"• ×{issue.count} {issue.logger_name}: {issue.sample[:120]}")
        lines.append("")

    resources = snapshot.resources
    database = snapshot.database
    memory = (
        f"{resources.memory_percent:.0f}%" if resources.memory_percent is not None else "—"
    )
    disk = f"{resources.disk_percent:.0f}%" if resources.disk_percent is not None else "—"
    latency = f"{database.latency_ms:.0f}ms" if database.latency_ms is not None else "—"
    lines.append(f"📊 RAM {memory} | Disk {disk} | DB {latency}")
    lines.append(
        f"🕐 {snapshot.taken_at.strftime('%H:%M')} | بازه {snapshot.window_seconds // 60} دقیقه"
    )
    return "\n".join(lines)
