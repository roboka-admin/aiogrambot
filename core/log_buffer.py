"""In-memory ring buffer of WARNING+ log records, grouped by fingerprint.

The monitoring layer needs "what went wrong recently" without shipping raw
logs anywhere. This handler keeps a bounded window of recent warnings and
errors and groups them by a stable *fingerprint* (logger + level + the
unformatted message template + exception type) so that a burst of the same
failure counts as one issue with a counter instead of hundreds of lines.

Everything is in memory on purpose: it is cheap, survives no restart, and
is exactly what an alert needs. Persisting history is a separate concern.
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from core.timezone import tehran_now

_SAMPLE_MAX_CHARS = 300
_DEFAULT_IGNORED_LOGGERS: tuple[str, ...] = (
    # aiogram logs "Update ... is not handled" at WARNING for every update
    # no handler matched; that is user behaviour, not a fault.
    "aiogram.event",
)


@dataclass(frozen=True, slots=True)
class LogIssue:
    """One distinct problem seen in the buffer window."""

    fingerprint: str
    level: str
    logger_name: str
    sample: str
    count: int
    first_seen_at: datetime
    last_seen_at: datetime
    exc_type: str = ""
    # True when this fingerprint was seen at ERROR+ for the first time since
    # process start inside the queried window: "a new kind of failure".
    is_new: bool = False


IssueListener = Callable[[LogIssue], None]


@dataclass(slots=True)
class _Entry:
    fingerprint: str
    level: str
    levelno: int
    logger_name: str
    sample: str
    seen_at: datetime
    exc_type: str = ""
    is_new: bool = False


class ErrorLogBuffer(logging.Handler):
    """Collect WARNING+ records into a bounded buffer for later summarising."""

    def __init__(
        self,
        *,
        max_entries: int = 1000,
        ignored_loggers: tuple[str, ...] = _DEFAULT_IGNORED_LOGGERS,
    ) -> None:
        super().__init__(level=logging.WARNING)
        self._entries: deque[_Entry] = deque(maxlen=max_entries)
        self._ignored_loggers = ignored_loggers
        self._lock = threading.Lock()
        self._known_error_fingerprints: set[str] = set()
        self._listeners: list[IssueListener] = []

    def subscribe(self, listener: IssueListener) -> None:
        """Get every ERROR+ record as a single-entry ``LogIssue``, synchronously.

        Called from whichever thread emitted the log record, so listeners must
        be cheap and thread-safe (hand off to an event loop, never block).
        """
        self._listeners.append(listener)

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno < logging.WARNING:
            return
        if any(
            record.name == name or record.name.startswith(f"{name}.")
            for name in self._ignored_loggers
        ):
            return

        try:
            sample = record.getMessage()
        except Exception:  # pragma: no cover - defensive, mirrors logging
            sample = str(record.msg)

        exc_type = ""
        if record.exc_info and record.exc_info[0] is not None:
            exc_type = record.exc_info[0].__name__
            sample = f"{sample} [{exc_type}]"

        fingerprint = f"{record.name}|{record.levelname}|{record.msg}|{exc_type}"
        entry = _Entry(
            fingerprint=fingerprint,
            level=record.levelname,
            levelno=record.levelno,
            logger_name=record.name,
            sample=sample[:_SAMPLE_MAX_CHARS],
            seen_at=tehran_now(),
            exc_type=exc_type,
        )
        with self._lock:
            if entry.levelno >= logging.ERROR and fingerprint not in self._known_error_fingerprints:
                self._known_error_fingerprints.add(fingerprint)
                entry.is_new = True
            self._entries.append(entry)

        if entry.levelno >= logging.ERROR and self._listeners:
            issue = _issue_from_entries([entry])
            for listener in self._listeners:
                try:
                    listener(issue)
                except Exception:  # pragma: no cover - a listener must never break logging
                    pass

    def issues_since(self, since: datetime) -> list[LogIssue]:
        """Group entries seen at or after ``since``; most frequent first."""
        with self._lock:
            entries = [entry for entry in self._entries if entry.seen_at >= since]

        grouped: dict[str, list[_Entry]] = {}
        for entry in entries:
            grouped.setdefault(entry.fingerprint, []).append(entry)

        issues = [_issue_from_entries(group) for group in grouped.values()]
        issues.sort(key=lambda issue: (-issue.count, issue.last_seen_at))
        return issues

    def count_since(self, since: datetime, *, min_level: int = logging.WARNING) -> int:
        with self._lock:
            return sum(
                1
                for entry in self._entries
                if entry.seen_at >= since and entry.levelno >= min_level
            )


def _issue_from_entries(group: list[_Entry]) -> LogIssue:
    last = group[-1]
    return LogIssue(
        fingerprint=last.fingerprint,
        level=last.level,
        logger_name=last.logger_name,
        sample=last.sample,
        count=len(group),
        first_seen_at=group[0].seen_at,
        last_seen_at=last.seen_at,
        exc_type=last.exc_type,
        is_new=any(entry.is_new for entry in group),
    )
