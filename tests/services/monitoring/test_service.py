import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

import pytest

from core.log_buffer import ErrorLogBuffer
from core.timezone import tehran_now
from models.antispam import AntiSpamEventType
from services.monitoring import MonitoringService
from services.system import SystemStats
from services.telegram import TelegramGatewayError


class FakeSystemService:
    def __init__(self) -> None:
        self.memory_percent: float | None = 40.0
        self.total_updates = 0
        self.total_errors = 0
        self.database_healthy = True

    async def get_system_statistics(self) -> SystemStats:
        now = tehran_now()
        return SystemStats(
            bot_started_at=now,
            current_time=now,
            uptime_seconds=10,
            server_uptime_seconds=None,
            total_updates=self.total_updates,
            total_errors=self.total_errors,
            cpu_percent=5.0,
            memory_percent=self.memory_percent,
            memory_used_mb=200,
            memory_total_mb=512,
            disk_percent=30.0,
            disk_used_gb=0.5,
            disk_total_gb=2.0,
            database_healthy=self.database_healthy,
            db_table_count=5,
            db_row_count=10,
            db_latency_ms=15.0,
            db_size_mb=1.0,
        )


class FakeUserRepository:
    def __init__(self) -> None:
        self.bot_blocked_since = 0
        self.bot_blocked_total = 0
        self.blocked = 0

    async def count_blocked(self) -> int:
        return self.blocked

    async def count_bot_blocked(self) -> int:
        return self.bot_blocked_total

    async def count_bot_blocked_since(self, since: datetime) -> int:
        return self.bot_blocked_since


class FakeAntiSpamRepository:
    def __init__(self) -> None:
        self.warnings = 0
        self.blocks = 0

    async def count_since(self, since: datetime, event_type: AntiSpamEventType) -> int:
        return self.blocks if event_type is AntiSpamEventType.BLOCK else self.warnings


class FakeGateway:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []
        self.fail_for: set[int] = set()

    async def send_message(self, telegram_id: int, text: str) -> None:
        if telegram_id in self.fail_for:
            raise TelegramGatewayError("nope")
        self.messages.append((telegram_id, text))


def build(
    *,
    system: FakeSystemService | None = None,
    cooldown: timedelta = timedelta(hours=1),
) -> tuple[MonitoringService, FakeSystemService, FakeGateway, FakeUserRepository, FakeAntiSpamRepository]:
    system = system or FakeSystemService()
    gateway = FakeGateway()
    users = FakeUserRepository()
    antispam = FakeAntiSpamRepository()

    @asynccontextmanager
    async def scope():
        yield users, antispam

    async def admins() -> tuple[int, ...]:
        return (100, 200)

    service = MonitoringService(
        system_service=system,  # type: ignore[arg-type]
        log_buffer=ErrorLogBuffer(),
        telegram_gateway=gateway,
        repository_factory=scope,
        admin_ids_provider=admins,
        alert_cooldown=cooldown,
    )
    return service, system, gateway, users, antispam


@pytest.mark.asyncio
async def test_healthy_cycle_sends_nothing() -> None:
    service, _, gateway, _, _ = build()

    snapshot, anomalies = await service.run_cycle()

    assert anomalies == []
    assert gateway.messages == []
    assert service.last_snapshot is snapshot


@pytest.mark.asyncio
async def test_anomaly_alerts_all_admins_once_and_respects_cooldown() -> None:
    service, system, gateway, _, _ = build()
    system.memory_percent = 95.0

    await service.run_cycle()
    await service.run_cycle()

    assert [admin for admin, _ in gateway.messages] == [100, 200]
    text = gateway.messages[0][1]
    assert "🚨" in text
    assert "حافظه" in text
    assert "RAM 95%" in text


@pytest.mark.asyncio
async def test_alert_repeats_after_cooldown_and_reports_resolution() -> None:
    service, system, gateway, _, _ = build(cooldown=timedelta(seconds=0))
    system.memory_percent = 95.0

    await service.run_cycle()
    await service.run_cycle()
    assert len(gateway.messages) == 4  # two cycles × two admins

    system.memory_percent = 40.0
    await service.run_cycle()

    assert len(gateway.messages) == 6
    assert "✅ برطرف شد: مصرف حافظه (RAM) بالاست" in gateway.messages[-1][1]

    await service.run_cycle()
    assert len(gateway.messages) == 6  # nothing new once resolved


@pytest.mark.asyncio
async def test_window_counters_are_deltas_between_cycles() -> None:
    service, system, _, users, antispam = build()
    system.total_updates = 100
    system.total_errors = 2
    await service.run_cycle()

    system.total_updates = 130
    system.total_errors = 9
    users.bot_blocked_since = 3
    antispam.blocks = 2
    snapshot, anomalies = await service.run_cycle()

    assert snapshot.activity.updates == 30
    assert snapshot.activity.errors == 7
    assert snapshot.activity.bot_blocked_by_users == 3
    assert snapshot.activity.spam_blocks == 2
    assert [a.key for a in anomalies] == ["errors"]


@pytest.mark.asyncio
async def test_recent_log_issues_are_included_in_alert() -> None:
    service, system, gateway, _, _ = build()
    system.memory_percent = 95.0
    logger = logging.getLogger("test.monitoring.issue")
    logger.handlers = [service._log_buffer]
    logger.propagate = False
    logger.warning("Broadcast failed for user %s", 7)

    snapshot, _ = await service.run_cycle()

    assert snapshot.issues[0].count == 1
    assert "Broadcast failed for user 7" in gateway.messages[0][1]


@pytest.mark.asyncio
async def test_delivery_failure_to_one_admin_does_not_stop_others() -> None:
    service, system, gateway, _, _ = build()
    system.memory_percent = 95.0
    gateway.fail_for = {100}

    await service.run_cycle()

    assert [admin for admin, _ in gateway.messages] == [200]


@pytest.mark.asyncio
async def test_repository_failure_still_produces_snapshot() -> None:
    system = FakeSystemService()
    system.database_healthy = False
    gateway = FakeGateway()

    @asynccontextmanager
    async def broken_scope():
        raise RuntimeError("db down")
        yield  # pragma: no cover

    async def admins() -> tuple[int, ...]:
        return (100,)

    service = MonitoringService(
        system_service=system,  # type: ignore[arg-type]
        log_buffer=ErrorLogBuffer(),
        telegram_gateway=gateway,
        repository_factory=broken_scope,
        admin_ids_provider=admins,
    )

    snapshot, anomalies = await service.run_cycle()

    assert snapshot.activity.spam_blocks == 0
    assert [a.key for a in anomalies] == ["db_down"]
    assert "پایگاه داده" in gateway.messages[0][1]


class FakeAnalyzer:
    def __init__(self, *, enabled: bool = True, digest: bool = False, text: str = "تشخیص: تست") -> None:
        self.enabled = enabled
        self.digest = digest
        self.text = text
        self.calls: list[tuple[str, list[str]]] = []

    async def is_enabled(self) -> bool:
        return self.enabled

    async def digest_due(self, now) -> bool:
        return self.digest

    async def analyse(self, snapshot, anomalies, *, kind):
        from models.ai import AIReport
        from services.monitoring.analysis import AIAnalysis

        self.calls.append((kind.value, [a.key for a in anomalies]))
        report = AIReport(
            id=1, kind=kind, provider_key="gemini", severity="warning", summary=self.text,
            anomaly_keys=",".join(a.key for a in anomalies), tokens_in=100, tokens_out=30,
        )
        return AIAnalysis(report=report, switched_from="mistral" if kind.value == "anomaly" else None)


def build_with_analyzer(analyzer: FakeAnalyzer, **kwargs):
    service, system, gateway, users, antispam = build(**kwargs)
    service._analyzer = analyzer  # injected the same way main.py does via constructor
    return service, system, gateway


@pytest.mark.asyncio
async def test_ai_diagnosis_is_appended_only_for_newly_reported_anomalies() -> None:
    analyzer = FakeAnalyzer()
    service, system, gateway = build_with_analyzer(analyzer)
    system.memory_percent = 95.0

    await service.run_cycle()
    await service.run_cycle()  # still failing, inside cooldown → no new alert, no AI call

    assert analyzer.calls == [("anomaly", ["memory"])]
    text = gateway.messages[0][1]
    assert "🤖 تحلیل هوشمند (gemini):" in text
    assert "تشخیص: تست" in text
    assert "↪️ مدل mistral در دسترس نبود؛ به gemini سوئیچ شد." in text
    assert "🔢 توکن: 130" in text


@pytest.mark.asyncio
async def test_ai_is_skipped_when_disabled_but_alert_still_sent() -> None:
    analyzer = FakeAnalyzer(enabled=False)
    service, system, gateway = build_with_analyzer(analyzer)
    system.memory_percent = 95.0

    await service.run_cycle()

    assert analyzer.calls == []
    assert len(gateway.messages) == 2
    assert "تحلیل هوشمند" not in gateway.messages[0][1]


@pytest.mark.asyncio
async def test_digest_is_sent_when_due_even_without_anomalies() -> None:
    analyzer = FakeAnalyzer(digest=True, text="تشخیص: همه‌چیز سالم است")
    service, _, gateway = build_with_analyzer(analyzer)

    await service.run_cycle()

    assert analyzer.calls == [("digest", [])]
    assert gateway.messages[0][1].startswith("📋 گزارش دوره‌ای سلامت ربات")
    assert "همه‌چیز سالم است" in gateway.messages[0][1]


@pytest.mark.asyncio
async def test_analyse_now_returns_manual_report_without_sending() -> None:
    analyzer = FakeAnalyzer()
    service, system, gateway = build_with_analyzer(analyzer)
    system.memory_percent = 95.0

    snapshot, anomalies, analysis = await service.analyse_now()

    assert [a.key for a in anomalies] == ["memory"]
    assert analysis is not None and analysis.report.kind.value == "manual"
    assert gateway.messages == []
