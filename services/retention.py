"""Bounded growth for append-only event tables.

Three tables only ever receive INSERTs and are read back as counts over
windows of at most 30 days: ``antispam_events``,
``force_subscription_membership_events`` and ``ai_reports``. Without a
retention policy they grow with traffic forever, and every "all time" COUNT
gets slower with them.

Policy: rows older than ``retention_days`` are deleted in small batches; the
number of rows removed is folded into ``event_counters`` inside the same
transaction, so lifetime totals shown to admins stay exact
(``total = archived + live``). Business tables (users, support tickets,
referral ledger) are deliberately out of scope.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from core.timezone import tehran_now
from models import event_counter as counters
from models.antispam import AntiSpamEventType
from repositories.interfaces.ai import IAIReportRepository
from repositories.interfaces.antispam import IAntiSpamRepository
from repositories.interfaces.event_counter import IEventCounterRepository
from repositories.interfaces.force_subscription_event import IForceSubscriptionEventRepository

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = 90
DEFAULT_BATCH_SIZE = 5000
# Upper bound on batches per run so one pass can never hog the DB; the
# remainder is picked up by the next scheduled run.
DEFAULT_MAX_BATCHES = 20


@dataclass(slots=True)
class RetentionRepositories:
    antispam: IAntiSpamRepository
    membership: IForceSubscriptionEventRepository
    ai_reports: IAIReportRepository
    counters: IEventCounterRepository


RetentionScope = Callable[[], AbstractAsyncContextManager[RetentionRepositories]]


@dataclass(slots=True)
class RetentionResult:
    cutoff: datetime
    deleted: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.deleted.values())


class RetentionService:
    def __init__(
        self,
        *,
        scope: RetentionScope,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_batches: int = DEFAULT_MAX_BATCHES,
    ) -> None:
        if retention_days < 31:
            # Admin statistics look back 30 days; pruning inside that window
            # would silently corrupt "last 30 days".
            raise ValueError("retention_days must be at least 31")
        self._scope = scope
        self._retention = timedelta(days=retention_days)
        self._batch_size = batch_size
        self._max_batches = max_batches

    async def run_once(self, now: datetime | None = None) -> RetentionResult:
        """Prune every table once; never raises (logs and moves on)."""
        cutoff = (now or tehran_now()) - self._retention
        result = RetentionResult(cutoff=cutoff)
        for name, step in (
            ("antispam_events", self._prune_antispam),
            ("membership_events", self._prune_membership),
            ("ai_reports", self._prune_ai_reports),
        ):
            try:
                result.deleted[name] = await step(cutoff)
            except Exception:
                logger.exception("Retention step %s failed", name)
                result.deleted[name] = 0
        if result.total:
            logger.info("Retention pruned %s rows older than %s", result.total, cutoff.date())
        return result

    # Each batch is its own short transaction: delete + counter update commit
    # together, so a crash mid-run can never lose or double-count rows.

    async def _prune_antispam(self, cutoff: datetime) -> int:
        total = 0
        for event_type, counter_kind in (
            (AntiSpamEventType.WARNING, counters.ANTISPAM_WARNINGS),
            (AntiSpamEventType.BLOCK, counters.ANTISPAM_BLOCKS),
        ):
            total += await self._batched(
                lambda repos, limit, et=event_type: repos.antispam.delete_before(cutoff, et, limit),
                counter_kind,
            )
        return total

    async def _prune_membership(self, cutoff: datetime) -> int:
        async with self._scope() as repos:
            target_ids = await repos.membership.list_target_ids_before(cutoff)
        total = 0
        for target_id in target_ids:
            deleted = await self._batched(
                lambda repos, limit, tid=target_id: repos.membership.delete_before(cutoff, tid, limit),
                counters.membership_target_kind(target_id),
                extra_counter=counters.MEMBERSHIP_EVENTS,
            )
            total += deleted
        return total

    async def _prune_ai_reports(self, cutoff: datetime) -> int:
        # No lifetime total is shown for reports, so nothing to archive.
        return await self._batched(
            lambda repos, limit: repos.ai_reports.delete_before(cutoff, limit), counter_kind=None
        )

    async def _batched(
        self,
        delete_batch,
        counter_kind: str | None,
        *,
        extra_counter: str | None = None,
    ) -> int:
        total = 0
        for _ in range(self._max_batches):
            async with self._scope() as repos:
                deleted = await delete_batch(repos, self._batch_size)
                if deleted and counter_kind is not None:
                    await repos.counters.add(counter_kind, deleted)
                if deleted and extra_counter is not None:
                    await repos.counters.add(extra_counter, deleted)
            total += deleted
            if deleted < self._batch_size:
                break
        return total
