"""AI layer on top of rule-based monitoring.

The model never sees raw logs. It receives a compact JSON snapshot plus the
anomalies that fired and returns a short Persian diagnosis. It is invoked
only when the rules report something new or when a scheduled digest is due,
so token spend stays proportional to real events, not to uptime.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime, timedelta

from core.timezone import ensure_tehran, tehran_now
from models.ai import AIReport, AIReportKind
from repositories.interfaces.ai import IAIReportRepository
from repositories.interfaces.bot_settings import IBotSettingsRepository
from services.ai.provider import AIRequest
from services.ai.router import AIRouter, NoProviderAvailable
from services.monitoring.rules import Anomaly, Severity
from services.monitoring.snapshot import MonitoringSnapshot

logger = logging.getLogger(__name__)

AnalysisRepositoryFactory = Callable[
    [], AbstractAsyncContextManager[tuple[IAIReportRepository, IBotSettingsRepository]]
]

_MAX_OUTPUT_TOKENS = 350
_URGENT_OUTPUT_TOKENS = 200
_MAX_ISSUES = 5
_MAX_SAMPLE_CHARS = 160

SYSTEM_PROMPT = (
    "You are the on-call SRE for a small Telegram bot (Python/aiogram, MySQL) "
    "running in a 512MB container. You receive a JSON health snapshot and the "
    "anomalies detected by threshold rules. Reply in Persian, plain text, no "
    "markdown, at most 120 words, using exactly this layout:\n"
    "تشخیص: <one sentence>\n"
    "علت محتمل: <one or two short items>\n"
    "اقدام پیشنهادی: <one to three concrete steps>\n"
    "If nothing is wrong, say so in one line under تشخیص and keep the other "
    "two lines very short. Never suggest actions you cannot justify from the data."
)

DIGEST_INSTRUCTION = (
    "This is a scheduled periodic digest, not an incident. Summarise the "
    "overall health trend and mention anything worth watching."
)
ANOMALY_INSTRUCTION = "These anomalies were just detected. Diagnose them."
URGENT_INSTRUCTION = (
    "URGENT triage: a serious error just appeared in the logs (see anomalies/"
    "issues). Focus on that error only: is the bot likely broken for users, "
    "what most probably caused it, what to check first. Be brief."
)


@dataclass(frozen=True, slots=True)
class AIAnalysis:
    report: AIReport
    switched_from: str | None


class AIAnalyzer:
    def __init__(
        self,
        *,
        router: AIRouter,
        repository_factory: AnalysisRepositoryFactory,
    ) -> None:
        self._router = router
        self._repository_factory = repository_factory

    async def is_enabled(self) -> bool:
        async with self._repository_factory() as (_, settings_repository):
            settings = await settings_repository.get()
        return settings is None or settings.ai_monitoring_enabled

    async def digest_due(self, now: datetime | None = None) -> bool:
        now = now or tehran_now()
        async with self._repository_factory() as (reports, settings_repository):
            settings = await settings_repository.get()
            if settings is not None and not settings.ai_monitoring_enabled:
                return False
            interval_hours = settings.ai_digest_interval_hours if settings else 24
            latest = await reports.get_latest(AIReportKind.DIGEST.value)
        if latest is None:
            return True
        return now - ensure_tehran(latest.created_at) >= timedelta(hours=interval_hours)

    async def analyse(
        self,
        snapshot: MonitoringSnapshot,
        anomalies: list[Anomaly],
        *,
        kind: AIReportKind,
    ) -> AIAnalysis | None:
        """Ask the active model for a diagnosis; ``None`` when unavailable.

        Never raises: monitoring alerts must go out even if every provider is
        down, so failures are logged and swallowed here.
        """
        request = AIRequest(
            system=SYSTEM_PROMPT,
            user=build_user_prompt(snapshot, anomalies, kind=kind),
            max_tokens=_URGENT_OUTPUT_TOKENS if kind is AIReportKind.URGENT else _MAX_OUTPUT_TOKENS,
        )
        try:
            result = await self._router.complete(request)
        except NoProviderAvailable as exc:
            logger.warning("AI analysis skipped: %s", exc)
            return None
        except Exception:
            logger.exception("AI analysis failed unexpectedly")
            return None

        report = AIReport(
            id=None,
            kind=kind,
            provider_key=result.provider_key,
            severity=_max_severity(anomalies),
            summary=result.response.text or "(پاسخ خالی)",
            anomaly_keys=",".join(anomaly.key for anomaly in anomalies),
            tokens_in=result.response.tokens_in,
            tokens_out=result.response.tokens_out,
            created_at=snapshot.taken_at,
        )
        try:
            async with self._repository_factory() as (reports, _):
                report = await reports.create(report)
        except Exception:
            logger.exception("Could not persist AI report")
        return AIAnalysis(report=report, switched_from=result.switched_from)


def build_user_prompt(
    snapshot: MonitoringSnapshot, anomalies: list[Anomaly], *, kind: AIReportKind
) -> str:
    """Compact JSON: numbers only, short issue samples, no prose."""
    resources = snapshot.resources
    database = snapshot.database
    activity = snapshot.activity
    payload = {
        "window_min": snapshot.window_seconds // 60,
        "uptime_h": round(snapshot.uptime_seconds / 3600, 1),
        "res": {
            "cpu": resources.cpu_percent,
            "mem_pct": resources.memory_percent,
            "mem_mb": [resources.memory_used_mb, resources.memory_total_mb],
            "disk_pct": resources.disk_percent,
        },
        "db": {
            "ok": database.healthy,
            "latency_ms": database.latency_ms,
            "size_mb": database.size_mb,
        },
        "act": {
            "updates": activity.updates,
            "errors": activity.errors,
            "spam_warn": activity.spam_warnings,
            "spam_block": activity.spam_blocks,
            "blocked_bot": activity.bot_blocked_by_users,
            "blocked_bot_total": activity.bot_blocked_by_users_total,
        },
        "anomalies": [
            {"key": anomaly.key, "sev": anomaly.severity.value, "detail": anomaly.detail}
            for anomaly in anomalies
        ],
        "issues": [
            {
                "n": issue.count,
                "lvl": issue.level,
                "src": issue.logger_name,
                "msg": issue.sample[:_MAX_SAMPLE_CHARS],
            }
            for issue in snapshot.issues[:_MAX_ISSUES]
        ],
    }
    if kind is AIReportKind.DIGEST:
        instruction = DIGEST_INSTRUCTION
    elif kind is AIReportKind.URGENT:
        instruction = URGENT_INSTRUCTION
    else:
        instruction = ANOMALY_INSTRUCTION
    return f"{instruction}\n{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}"


def _max_severity(anomalies: list[Anomaly]) -> str:
    if any(anomaly.severity is Severity.CRITICAL for anomaly in anomalies):
        return Severity.CRITICAL.value
    if anomalies:
        return Severity.WARNING.value
    return "info"
