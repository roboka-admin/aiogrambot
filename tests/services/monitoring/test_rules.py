from dataclasses import replace
from datetime import timedelta

from core.log_buffer import LogIssue
from core.timezone import tehran_now
from services.monitoring.rules import Severity, Thresholds, evaluate, is_urgent_issue
from services.monitoring.snapshot import (
    ActivityMetrics,
    DatabaseMetrics,
    MonitoringSnapshot,
    ResourceMetrics,
)


def make_snapshot(
    *,
    memory_percent: float | None = 40.0,
    disk_percent: float | None = 40.0,
    cpu_percent: float | None = 10.0,
    db_healthy: bool = True,
    db_latency_ms: float | None = 20.0,
    updates: int = 0,
    errors: int = 0,
    spam_warnings: int = 0,
    spam_blocks: int = 0,
    bot_blocked: int = 0,
) -> MonitoringSnapshot:
    now = tehran_now()
    return MonitoringSnapshot(
        taken_at=now,
        window_start=now - timedelta(minutes=5),
        window_seconds=300,
        uptime_seconds=1000,
        resources=ResourceMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_used_mb=100,
            memory_total_mb=512,
            disk_percent=disk_percent,
            disk_used_gb=1.0,
            disk_total_gb=2.0,
        ),
        database=DatabaseMetrics(
            healthy=db_healthy, latency_ms=db_latency_ms, size_mb=1.0, row_count=10
        ),
        activity=ActivityMetrics(
            updates=updates,
            errors=errors,
            spam_warnings=spam_warnings,
            spam_blocks=spam_blocks,
            admin_blocks_total=0,
            bot_blocked_by_users=bot_blocked,
            bot_blocked_by_users_total=0,
        ),
    )


def _keys(snapshot: MonitoringSnapshot) -> dict[str, Severity]:
    return {anomaly.key: anomaly.severity for anomaly in evaluate(snapshot)}


def test_healthy_snapshot_has_no_anomalies() -> None:
    assert evaluate(make_snapshot()) == []


def test_database_down_is_critical_and_skips_latency_rule() -> None:
    keys = _keys(make_snapshot(db_healthy=False, db_latency_ms=None))
    assert keys == {"db_down": Severity.CRITICAL}


def test_database_latency_thresholds() -> None:
    assert _keys(make_snapshot(db_latency_ms=600))["db_latency"] is Severity.WARNING
    assert _keys(make_snapshot(db_latency_ms=2500))["db_latency"] is Severity.CRITICAL


def test_memory_and_disk_thresholds() -> None:
    assert _keys(make_snapshot(memory_percent=85))["memory"] is Severity.WARNING
    assert _keys(make_snapshot(memory_percent=95))["memory"] is Severity.CRITICAL
    assert _keys(make_snapshot(disk_percent=90))["disk"] is Severity.WARNING
    assert _keys(make_snapshot(disk_percent=96))["disk"] is Severity.CRITICAL
    assert "memory" not in _keys(make_snapshot(memory_percent=None))


def test_error_rules_use_count_and_rate() -> None:
    assert _keys(make_snapshot(errors=5))["errors"] is Severity.WARNING
    assert _keys(make_snapshot(errors=30))["errors"] is Severity.CRITICAL
    # 3 errors alone is fine, but 3 of 20 updates is a 15% error rate.
    assert "errors" not in _keys(make_snapshot(errors=3))
    assert _keys(make_snapshot(errors=3, updates=20))["errors"] is Severity.WARNING


def test_spam_and_bot_blocked_rules() -> None:
    assert "spam_blocks" in _keys(make_snapshot(spam_blocks=5))
    assert "spam_warnings" in _keys(make_snapshot(spam_warnings=30))
    assert "spam_warnings" not in _keys(make_snapshot(spam_warnings=30, spam_blocks=5))
    assert "bot_blocked" in _keys(make_snapshot(bot_blocked=10))


def test_custom_thresholds_are_respected() -> None:
    thresholds = Thresholds(memory_warning_percent=30, memory_critical_percent=35)
    anomalies = evaluate(make_snapshot(memory_percent=32), thresholds)
    assert [a.key for a in anomalies] == ["memory"]
    assert anomalies[0].severity is Severity.WARNING
    assert "32%" in anomalies[0].detail


def _issue(level="ERROR", exc_type="", is_new=False, sample="boom", count=1) -> LogIssue:
    now = tehran_now()
    return LogIssue(
        fingerprint=f"app|{level}|{sample}|{exc_type}",
        level=level,
        logger_name="app",
        sample=sample,
        count=count,
        first_seen_at=now,
        last_seen_at=now,
        exc_type=exc_type,
        is_new=is_new,
    )


def test_fatal_exception_type_is_critical_even_when_seen_once_and_not_new():
    snapshot = replace(make_snapshot(), issues=(_issue(exc_type="OperationalError"),))
    anomalies = evaluate(snapshot)
    assert len(anomalies) == 1
    assert anomalies[0].severity is Severity.CRITICAL
    assert anomalies[0].key.startswith("fatal_error:")
    assert anomalies[0].transient is True
    assert "OperationalError" in anomalies[0].title


def test_new_error_fingerprint_is_a_warning_but_repeats_and_warnings_are_not():
    snapshot = replace(
        make_snapshot(),
        issues=(
            _issue(is_new=True, sample="first time"),
            _issue(is_new=False, sample="seen before", count=40),
            _issue(level="WARNING", is_new=True, sample="just a warning"),
        ),
    )
    anomalies = evaluate(snapshot)
    assert [a.severity for a in anomalies] == [Severity.WARNING]
    assert anomalies[0].key.startswith("new_error:")
    assert "first time" in anomalies[0].detail


def test_distinct_fatal_errors_get_distinct_keys():
    snapshot = replace(
        make_snapshot(),
        issues=(
            _issue(exc_type="OperationalError", sample="a"),
            _issue(exc_type="TelegramUnauthorized", sample="b"),
        ),
    )
    keys = {a.key for a in evaluate(snapshot)}
    assert len(keys) == 2


def test_is_urgent_issue_matches_fast_path_policy():
    assert is_urgent_issue(_issue(exc_type="MemoryError")) is True
    assert is_urgent_issue(_issue(is_new=True)) is True
    assert is_urgent_issue(_issue(is_new=False)) is False
    assert is_urgent_issue(_issue(level="WARNING", is_new=True)) is False
