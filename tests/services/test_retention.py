from contextlib import asynccontextmanager
from datetime import datetime, timedelta

import pytest

from core.timezone import tehran_now
from models import event_counter as counters
from models.antispam import AntiSpamEventType
from services.retention import RetentionRepositories, RetentionService


class FakeAntiSpam:
    def __init__(self) -> None:
        self.rows: list[tuple[datetime, AntiSpamEventType]] = []

    async def delete_before(self, cutoff, event_type, limit) -> int:
        victims = [r for r in self.rows if r[0] < cutoff and r[1] is event_type][:limit]
        for victim in victims:
            self.rows.remove(victim)
        return len(victims)


class FakeMembership:
    def __init__(self) -> None:
        self.rows: list[tuple[datetime, int]] = []

    async def list_target_ids_before(self, cutoff) -> list[int]:
        return sorted({target for created, target in self.rows if created < cutoff})

    async def delete_before(self, cutoff, target_chat_id, limit) -> int:
        victims = [r for r in self.rows if r[0] < cutoff and r[1] == target_chat_id][:limit]
        for victim in victims:
            self.rows.remove(victim)
        return len(victims)


class FakeReports:
    def __init__(self) -> None:
        self.rows: list[datetime] = []

    async def delete_before(self, cutoff, limit) -> int:
        victims = [r for r in self.rows if r < cutoff][:limit]
        for victim in victims:
            self.rows.remove(victim)
        return len(victims)


class FakeSupport:
    def __init__(self) -> None:
        self.rows: list[tuple[str, datetime | None]] = []  # (status, closed_at)

    async def delete_closed_before(self, cutoff, limit) -> int:
        victims = [
            r for r in self.rows if r[0] == "closed" and r[1] is not None and r[1] < cutoff
        ][:limit]
        for victim in victims:
            self.rows.remove(victim)
        return len(victims)


class FakeCounters:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}

    async def add(self, kind, amount) -> None:
        self.values[kind] = self.values.get(kind, 0) + amount

    async def get(self, kind) -> int:
        return self.values.get(kind, 0)


class Scope:
    """Counts transactions so batching behaviour is observable."""

    def __init__(self) -> None:
        self.repos = RetentionRepositories(
            antispam=FakeAntiSpam(),
            membership=FakeMembership(),
            ai_reports=FakeReports(),
            counters=FakeCounters(),
            support=FakeSupport(),
        )
        self.transactions = 0

    @asynccontextmanager
    async def __call__(self):
        self.transactions += 1
        yield self.repos


NOW = tehran_now()
OLD = NOW - timedelta(days=40)
RECENT = NOW - timedelta(days=10)


def make(scope: Scope, **kwargs) -> RetentionService:
    return RetentionService(scope=scope, retention_days=31, **kwargs)


async def test_old_rows_are_pruned_and_folded_into_counters_recent_rows_stay():
    scope = Scope()
    scope.repos.antispam.rows = [
        (OLD, AntiSpamEventType.WARNING),
        (OLD, AntiSpamEventType.WARNING),
        (OLD, AntiSpamEventType.BLOCK),
        (RECENT, AntiSpamEventType.WARNING),
    ]
    scope.repos.membership.rows = [(OLD, 1), (OLD, 1), (OLD, 2), (RECENT, 1)]
    scope.repos.ai_reports.rows = [OLD, RECENT]

    result = await make(scope).run_once(NOW)

    assert result.deleted == {
        "antispam_events": 3,
        "membership_events": 3,
        "ai_reports": 1,
        "support_tickets_closed": 0,
    }
    assert scope.repos.antispam.rows == [(RECENT, AntiSpamEventType.WARNING)]
    assert scope.repos.membership.rows == [(RECENT, 1)]
    assert scope.repos.ai_reports.rows == [RECENT]
    assert scope.repos.counters.values == {
        counters.ANTISPAM_WARNINGS: 2,
        counters.ANTISPAM_BLOCKS: 1,
        counters.membership_target_kind(1): 2,
        counters.membership_target_kind(2): 1,
        counters.MEMBERSHIP_EVENTS: 3,
    }


async def test_nothing_to_prune_touches_no_counters():
    scope = Scope()
    scope.repos.antispam.rows = [(RECENT, AntiSpamEventType.WARNING)]
    result = await make(scope).run_once(NOW)
    assert result.total == 0
    assert scope.repos.counters.values == {}


async def test_large_backlog_is_deleted_in_batches_each_in_its_own_transaction():
    scope = Scope()
    scope.repos.ai_reports.rows = [OLD] * 12
    service = make(scope, batch_size=5, max_batches=100)

    result = await service.run_once(NOW)

    assert result.deleted["ai_reports"] == 12
    # 5 + 5 + 2 -> three transactions for reports; antispam adds one per type,
    # membership one for the id lookup (no targets -> no delete batches),
    # closed tickets one empty batch.
    assert scope.transactions == 3 + 2 + 1 + 1


async def test_max_batches_bounds_one_run_and_the_rest_waits_for_next_run():
    scope = Scope()
    scope.repos.ai_reports.rows = [OLD] * 12
    service = make(scope, batch_size=5, max_batches=2)

    first = await service.run_once(NOW)
    assert first.deleted["ai_reports"] == 10
    assert len(scope.repos.ai_reports.rows) == 2

    second = await service.run_once(NOW)
    assert second.deleted["ai_reports"] == 2


async def test_failure_in_one_table_does_not_stop_the_others():
    scope = Scope()

    async def boom(*_args, **_kwargs):
        raise RuntimeError("table locked")

    scope.repos.antispam.delete_before = boom  # type: ignore[assignment]
    scope.repos.ai_reports.rows = [OLD]

    result = await make(scope).run_once(NOW)

    assert result.deleted["antispam_events"] == 0
    assert result.deleted["ai_reports"] == 1


async def test_only_old_closed_tickets_are_pruned_open_and_recent_stay():
    scope = Scope()
    scope.repos.support.rows = [
        ("closed", OLD),
        ("closed", OLD),
        ("closed", RECENT),
        ("open", None),
        ("closed", None),  # legacy row without close time: never guessed at
    ]

    result = await make(scope).run_once(NOW)

    assert result.deleted["support_tickets_closed"] == 2
    assert scope.repos.support.rows == [("closed", RECENT), ("open", None), ("closed", None)]
    assert scope.repos.counters.values[counters.SUPPORT_TICKETS_CLOSED] == 2


def test_retention_shorter_than_statistics_window_is_rejected():
    with pytest.raises(ValueError):
        RetentionService(scope=Scope(), retention_days=30)
