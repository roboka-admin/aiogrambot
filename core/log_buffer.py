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


@dataclass(slots=True)
class _Entry:
    fingerprint: str
    level: str
    levelno: int
    logger_name: str
    sample: str
    seen_at: datetime


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

        entry = _Entry(
            fingerprint=f"{record.name}|{record.levelname}|{record.msg}|{exc_type}",
            level=record.levelname,
            levelno=record.levelno,
            logger_name=record.name,
            sample=sample[:_SAMPLE_MAX_CHARS],
            seen_at=tehran_now(),
        )
        with self._lock:
            self._entries.append(entry)

    def issues_since(self, since: datetime) -> list[LogIssue]:
        """Group entries seen at or after ``since``; most frequent first."""
        with self._lock:
            entries = [entry for entry in self._entries if entry.seen_at >= since]

        grouped: dict[str, list[_Entry]] = {}
        for entry in entries:
            grouped.setdefault(entry.fingerprint, []).append(entry)

        issues = [
            LogIssue(
                fingerprint=fingerprint,
                level=group[-1].level,
                logger_name=group[-1].logger_name,
                sample=group[-1].sample,
                count=len(group),
                first_seen_at=group[0].seen_at,
                last_seen_at=group[-1].seen_at,
            )
            for fingerprint, group in grouped.items()
        ]
        issues.sort(key=lambda issue: (-issue.count, issue.last_seen_at))
        return issues

    def count_since(self, since: datetime, *, min_level: int = logging.WARNING) -> int:
        with self._lock:
            return sum(
                1
                for entry in self._entries
                if entry.seen_at >= since and entry.levelno >= min_level
            )
