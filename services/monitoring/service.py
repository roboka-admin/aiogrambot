"""Periodic health check: snapshot → rules → admin alerts.

Runs as a background task next to polling, outside any Telegram update, so
it opens its own short-lived repository scope per cycle (same pattern as
``BroadcastService``). Alerting policy:

- an anomaly notifies admins the first time it fires and again only after
  ``alert_cooldown`` while it keeps firing (no five-minute spam);
- when a previously reported anomaly clears, admins get one "resolved" note;
- alerts are best-effort: a failed delivery is logged, never raised.

Fast path ("urgent"): the log buffer pushes every ERROR+ record to
``on_log_issue``. Fatal exception types and first-time error fingerprints
schedule an out-of-band cycle within ``urgent_debounce`` (default 2 min),
capped at ``urgent_max_per_hour``. The rules guarantee delivery; the AI only
adds a short triage when it is available.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Awaitable, Callable, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta

from core.log_buffer import ErrorLogBuffer, LogIssue
from core.timezone import tehran_now
from models.ai import AIReportKind
from models.antispam import AntiSpamEventType
from repositories.interfaces.antispam import IAntiSpamRepository
from repositories.interfaces.user import IUserRepository
from services.monitoring.analysis import AIAnalysis, AIAnalyzer
from services.monitoring.rules import (
    DEFAULT_THRESHOLDS,
    Anomaly,
    Severity,
    Thresholds,
    evaluate,
    is_urgent_issue,
)
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
        analyzer: AIAnalyzer | None = None,
        thresholds: Thresholds = DEFAULT_THRESHOLDS,
        alert_cooldown: timedelta = timedelta(hours=1),
        urgent_debounce: timedelta = timedelta(minutes=2),
        urgent_max_per_hour: int = 5,
    ) -> None:
        self._system_service = system_service
        self._log_buffer = log_buffer
        self._telegram_gateway = telegram_gateway
        self._repository_factory = repository_factory
        self._admin_ids_provider = admin_ids_provider
        self._analyzer = analyzer
        self._thresholds = thresholds
        self._alert_cooldown = alert_cooldown
        self._urgent_debounce = urgent_debounce
        self._urgent_max_per_hour = urgent_max_per_hour
        self._urgent_runs: deque[datetime] = deque()
        self._urgent_task: asyncio.Future[None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        # Only one cycle at a time: scheduled and urgent share counters/state.
        self._cycle_lock = asyncio.Lock()

        self._last_cycle_at: datetime | None = None
        self._last_updates_total = 0
        self._last_errors_total = 0
        # anomaly key -> (when admins were last told, human title for "resolved")
        self._active_alerts: dict[str, tuple[datetime, str]] = {}
        # subset of the above that represent ongoing states (get a "resolved" note)
        self._resolvable_keys: set[str] = set()
        self._last_snapshot: MonitoringSnapshot | None = None
        self._last_anomalies: tuple[Anomaly, ...] = ()

    # ------------------------------------------------------------------ public

    @property
    def last_snapshot(self) -> MonitoringSnapshot | None:
        return self._last_snapshot

    @property
    def last_anomalies(self) -> tuple[Anomaly, ...]:
        return self._last_anomalies

    def attach_log_buffer(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Subscribe to the log buffer; call once from inside the running loop."""
        self._loop = loop or asyncio.get_running_loop()
        self._log_buffer.subscribe(self.on_log_issue)

    def on_log_issue(self, issue: LogIssue) -> None:
        """Thread-safe entry point invoked by the log buffer for every ERROR+."""
        if self._loop is None or self._loop.is_closed() or not is_urgent_issue(issue):
            return
        try:
            current = asyncio.get_running_loop()
        except RuntimeError:
            current = None
        if current is self._loop:
            self._schedule_urgent(issue)  # already on the loop thread (usual case)
        else:
            self._loop.call_soon_threadsafe(self._schedule_urgent, issue)

    async def run_cycle(self) -> tuple[MonitoringSnapshot, list[Anomaly]]:
        """Collect one snapshot, evaluate rules, notify admins; never raises."""
        async with self._cycle_lock:
            return await self._run_cycle_locked(urgent=False)

    async def run_urgent_cycle(self) -> tuple[MonitoringSnapshot, list[Anomaly]]:
        """Out-of-band cycle for the fast path; same pipeline, urgent framing."""
        async with self._cycle_lock:
            return await self._run_cycle_locked(urgent=True)

    async def _run_cycle_locked(self, *, urgent: bool) -> tuple[MonitoringSnapshot, list[Anomaly]]:
        snapshot = await self.collect_snapshot()
        anomalies = evaluate(snapshot, self._thresholds)
        self._last_snapshot = snapshot
        self._last_anomalies = tuple(anomalies)

        try:
            await self._notify(snapshot, anomalies, urgent=urgent)
        except Exception:
            logger.exception("Monitoring alert delivery failed")

        if not urgent:
            try:
                await self._maybe_send_digest(snapshot, anomalies)
            except Exception:
                logger.exception("Monitoring digest failed")
        return snapshot, anomalies

    # ------------------------------------------------------------- fast path

    def _schedule_urgent(self, issue: LogIssue) -> None:
        """Runs on the loop thread. Debounce + hourly cap, then spawn a task."""
        if self._urgent_task is not None and not self._urgent_task.done():
            return  # a run is already pending; it will see the latest state
        now = tehran_now()
        while self._urgent_runs and now - self._urgent_runs[0] >= timedelta(hours=1):
            self._urgent_runs.popleft()
        if len(self._urgent_runs) >= self._urgent_max_per_hour:
            logger.warning(
                "Urgent monitoring run suppressed (hourly cap %s): %s",
                self._urgent_max_per_hour,
                issue.sample[:80],
            )
            return
        # Debounce: at most one urgent run per window. Inside the window the
        # run is delayed to the window edge instead of dropped, so the newest
        # failure is still reported. Outside it, a short grace lets a burst of
        # related errors land in a single report.
        delay = self._urgent_grace_seconds()
        if self._urgent_runs:
            until_window_edge = (self._urgent_runs[-1] + self._urgent_debounce - now).total_seconds()
            delay = max(delay, until_window_edge)
        self._urgent_runs.append(now + timedelta(seconds=delay))
        self._urgent_task = asyncio.ensure_future(self._urgent_worker(delay))

    async def _urgent_worker(self, delay: float) -> None:
        await asyncio.sleep(delay)
        try:
            await self.run_urgent_cycle()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Urgent monitoring cycle failed")

    def _urgent_grace_seconds(self) -> float:
        return min(5.0, self._urgent_debounce.total_seconds() / 24)

    async def analyse_now(self) -> tuple[MonitoringSnapshot, list[Anomaly], AIAnalysis | None]:
        """Admin-triggered analysis of a fresh snapshot (no alert cooldown logic)."""
        snapshot = await self.collect_snapshot()
        anomalies = evaluate(snapshot, self._thresholds)
        self._last_snapshot = snapshot
        self._last_anomalies = tuple(anomalies)
        analysis = None
        if self._analyzer is not None:
            analysis = await self._analyzer.analyse(snapshot, anomalies, kind=AIReportKind.MANUAL)
        return snapshot, anomalies, analysis

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
            issues=_select_issues(self._log_buffer.issues_since(window_start)),
        )

    # ----------------------------------------------------------------- alerts

    async def _notify(
        self, snapshot: MonitoringSnapshot, anomalies: list[Anomaly], *, urgent: bool = False
    ) -> None:
        now = snapshot.taken_at
        current_keys = {anomaly.key for anomaly in anomalies}

        to_report = [
            anomaly
            for anomaly in anomalies
            if anomaly.key not in self._active_alerts
            or now - self._active_alerts[anomaly.key][0] >= self._alert_cooldown
        ]
        # Transient (log-based) alerts have no "resolved" moment: the line
        # simply leaves the window. Keep them in the cooldown map silently.
        resolved = [
            title
            for key, (_, title) in self._active_alerts.items()
            if key not in current_keys and key in self._resolvable_keys
        ]

        for key in [key for key in self._active_alerts if key not in current_keys]:
            reported_at, _ = self._active_alerts[key]
            if key in self._resolvable_keys or now - reported_at >= self._alert_cooldown:
                del self._active_alerts[key]
        for anomaly in to_report:
            self._active_alerts[anomaly.key] = (now, anomaly.title)
            if not anomaly.transient:
                self._resolvable_keys.add(anomaly.key)
        self._resolvable_keys &= set(self._active_alerts)

        if not to_report and not resolved:
            return

        analysis: AIAnalysis | None = None
        if to_report and self._analyzer is not None and await self._analyzer.is_enabled():
            kind = AIReportKind.URGENT if urgent else AIReportKind.ANOMALY
            analysis = await self._analyzer.analyse(snapshot, to_report, kind=kind)

        text = _format_alert(snapshot, to_report, resolved, analysis, urgent=urgent)
        await self._send_to_admins(text)

    async def _maybe_send_digest(self, snapshot: MonitoringSnapshot, anomalies: list[Anomaly]) -> None:
        if self._analyzer is None or not await self._analyzer.digest_due(snapshot.taken_at):
            return
        analysis = await self._analyzer.analyse(snapshot, anomalies, kind=AIReportKind.DIGEST)
        if analysis is None:
            return
        await self._send_to_admins(_format_digest(snapshot, analysis))

    async def _send_to_admins(self, text: str) -> None:
        for admin_id in await self._admin_ids_provider():
            try:
                await self._telegram_gateway.send_message(admin_id, text)
            except TelegramGatewayError as exc:
                logger.warning("Could not deliver monitoring alert to admin %s: %s", admin_id, exc)


def _select_issues(issues: list[LogIssue], limit: int = 5) -> tuple[LogIssue, ...]:
    """Urgent issues first so a single fatal line is never crowded out by noise."""
    return tuple(sorted(issues, key=lambda issue: (not is_urgent_issue(issue), -issue.count))[:limit])


def _format_alert(
    snapshot: MonitoringSnapshot,
    anomalies: list[Anomaly],
    resolved: list[str],
    analysis: AIAnalysis | None = None,
    *,
    urgent: bool = False,
) -> str:
    header = "🚨 هشدار فوری — خطای جدی در لاگ" if urgent else "🩺 مانیتور سلامت ربات"
    lines: list[str] = [header, ""]

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

    if analysis is not None:
        lines.extend(_format_analysis_lines(analysis))
        lines.append("")

    lines.extend(_format_footer(snapshot))
    return "\n".join(lines)


def _format_digest(snapshot: MonitoringSnapshot, analysis: AIAnalysis) -> str:
    lines = ["📋 گزارش دوره‌ای سلامت ربات", ""]
    lines.extend(_format_analysis_lines(analysis))
    lines.append("")
    lines.extend(_format_footer(snapshot))
    return "\n".join(lines)


def _format_analysis_lines(analysis: AIAnalysis) -> list[str]:
    report = analysis.report
    lines = [f"🤖 تحلیل هوشمند ({report.provider_key}):", report.summary]
    if analysis.switched_from:
        lines.append(f"↪️ مدل {analysis.switched_from} در دسترس نبود؛ به {report.provider_key} سوئیچ شد.")
    lines.append(f"🔢 توکن: {report.tokens_in + report.tokens_out:,}")
    return lines


def _format_footer(snapshot: MonitoringSnapshot) -> list[str]:
    resources = snapshot.resources
    database = snapshot.database
    memory = (
        f"{resources.memory_percent:.0f}%" if resources.memory_percent is not None else "—"
    )
    disk = f"{resources.disk_percent:.0f}%" if resources.disk_percent is not None else "—"
    latency = f"{database.latency_ms:.0f}ms" if database.latency_ms is not None else "—"
    return [
        f"📊 RAM {memory} | Disk {disk} | DB {latency}",
        f"🕐 {snapshot.taken_at.strftime('%H:%M')} | بازه {snapshot.window_seconds // 60} دقیقه",
    ]
