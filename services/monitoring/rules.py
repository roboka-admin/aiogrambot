"""Threshold rules that turn a snapshot into a list of anomalies.

Kept free of I/O so it is trivially unit-testable and, later, so the AI
layer can be handed *only* the anomalies that actually fired.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from services.monitoring.snapshot import MonitoringSnapshot


class Severity(str, Enum):
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class Anomaly:
    """One rule that fired.

    ``key`` is stable across cycles and is what alert cooldowns key on, so
    the same ongoing problem does not re-notify every five minutes.
    """

    key: str
    severity: Severity
    title: str
    detail: str


@dataclass(frozen=True, slots=True)
class Thresholds:
    memory_warning_percent: float = 80.0
    memory_critical_percent: float = 92.0
    disk_warning_percent: float = 85.0
    disk_critical_percent: float = 95.0
    cpu_warning_percent: float = 85.0
    db_latency_warning_ms: float = 500.0
    db_latency_critical_ms: float = 2000.0
    # Errors in the window; spikes are compared against updates too.
    errors_warning: int = 5
    errors_critical: int = 25
    error_rate_warning: float = 0.10  # errors / updates when updates >= 20
    spam_blocks_warning: int = 5
    spam_warnings_warning: int = 30
    bot_blocked_warning: int = 10


DEFAULT_THRESHOLDS = Thresholds()


def evaluate(snapshot: MonitoringSnapshot, thresholds: Thresholds = DEFAULT_THRESHOLDS) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    resources = snapshot.resources
    database = snapshot.database
    activity = snapshot.activity

    if not database.healthy:
        anomalies.append(
            Anomaly(
                key="db_down",
                severity=Severity.CRITICAL,
                title="پایگاه داده در دسترس نیست",
                detail="اتصال یا کوئری آزمایشی به دیتابیس شکست خورد.",
            )
        )
    elif database.latency_ms is not None:
        if database.latency_ms >= thresholds.db_latency_critical_ms:
            anomalies.append(
                Anomaly(
                    key="db_latency",
                    severity=Severity.CRITICAL,
                    title="پاسخ‌دهی دیتابیس بسیار کند است",
                    detail=f"تأخیر SELECT 1: {database.latency_ms:.0f}ms",
                )
            )
        elif database.latency_ms >= thresholds.db_latency_warning_ms:
            anomalies.append(
                Anomaly(
                    key="db_latency",
                    severity=Severity.WARNING,
                    title="پاسخ‌دهی دیتابیس کند شده",
                    detail=f"تأخیر SELECT 1: {database.latency_ms:.0f}ms",
                )
            )

    _check_percent(
        anomalies,
        key="memory",
        value=resources.memory_percent,
        warning=thresholds.memory_warning_percent,
        critical=thresholds.memory_critical_percent,
        title="مصرف حافظه (RAM) بالاست",
        detail=(
            f"{resources.memory_percent:.0f}% "
            f"({resources.memory_used_mb} / {resources.memory_total_mb} MB)"
            if resources.memory_percent is not None
            else ""
        ),
    )
    _check_percent(
        anomalies,
        key="disk",
        value=resources.disk_percent,
        warning=thresholds.disk_warning_percent,
        critical=thresholds.disk_critical_percent,
        title="فضای دیسک رو به اتمام است",
        detail=(
            f"{resources.disk_percent:.0f}% "
            f"({resources.disk_used_gb} / {resources.disk_total_gb} GB)"
            if resources.disk_percent is not None
            else ""
        ),
    )
    if resources.cpu_percent is not None and resources.cpu_percent >= thresholds.cpu_warning_percent:
        anomalies.append(
            Anomaly(
                key="cpu",
                severity=Severity.WARNING,
                title="مصرف CPU بالاست",
                detail=f"{resources.cpu_percent:.0f}%",
            )
        )

    if activity.errors >= thresholds.errors_critical:
        anomalies.append(
            Anomaly(
                key="errors",
                severity=Severity.CRITICAL,
                title="تعداد خطاها بسیار زیاد است",
                detail=_errors_detail(activity.errors, activity.updates),
            )
        )
    elif activity.errors >= thresholds.errors_warning or (
        activity.updates >= 20
        and activity.errors / activity.updates >= thresholds.error_rate_warning
    ):
        anomalies.append(
            Anomaly(
                key="errors",
                severity=Severity.WARNING,
                title="افزایش خطاها",
                detail=_errors_detail(activity.errors, activity.updates),
            )
        )

    if activity.spam_blocks >= thresholds.spam_blocks_warning:
        anomalies.append(
            Anomaly(
                key="spam_blocks",
                severity=Severity.WARNING,
                title="موج اسپم: مسدودسازی خودکار",
                detail=f"{activity.spam_blocks} کاربر در این بازه به‌خاطر اسپم مسدود شدند.",
            )
        )
    elif activity.spam_warnings >= thresholds.spam_warnings_warning:
        anomalies.append(
            Anomaly(
                key="spam_warnings",
                severity=Severity.WARNING,
                title="افزایش اخطارهای اسپم",
                detail=f"{activity.spam_warnings} اخطار اسپم در این بازه.",
            )
        )

    if activity.bot_blocked_by_users >= thresholds.bot_blocked_warning:
        anomalies.append(
            Anomaly(
                key="bot_blocked",
                severity=Severity.WARNING,
                title="ریزش کاربران: ربات بلاک شد",
                detail=f"{activity.bot_blocked_by_users} کاربر در این بازه ربات را بلاک کردند.",
            )
        )

    return anomalies


def _check_percent(
    anomalies: list[Anomaly],
    *,
    key: str,
    value: float | None,
    warning: float,
    critical: float,
    title: str,
    detail: str,
) -> None:
    if value is None:
        return
    if value >= critical:
        anomalies.append(Anomaly(key=key, severity=Severity.CRITICAL, title=title, detail=detail))
    elif value >= warning:
        anomalies.append(Anomaly(key=key, severity=Severity.WARNING, title=title, detail=detail))


def _errors_detail(errors: int, updates: int) -> str:
    if updates:
        return f"{errors} خطا در {updates} آپدیت ({errors / updates:.0%})"
    return f"{errors} خطا"
