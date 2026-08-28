"""Temporary in-memory anti-spam protection for messages and callbacks."""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Deque

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from config import ADMIN_IDS
from services.antispam import AntiSpamService
from services.user import UserService

MAX_UPDATES = 5
WINDOW_SECONDS = 3.0
COOLDOWN_STAGES = (3.0, 10.0, 30.0, 120.0)
MAX_SPAM_VIOLATIONS = 3
VIOLATION_RESET_SECONDS = 60.0
MAX_INACTIVE_SECONDS = 300.0
CLEANUP_INTERVAL_SECONDS = 60.0
WARNING_MESSAGE = "⚠️ لطفاً کمی آهسته‌تر عمل کنید و چند لحظه صبر کنید."
BLOCKED_MESSAGE = "🚫 به دلیل ارسال پیام‌های مکرر و اسپم، دسترسی شما به ربات مسدود شد."


@dataclass(slots=True)
class SpamState:
    """Rate-limit state for one user and one event type."""

    timestamps: Deque[float] = field(default_factory=deque)
    violation_level: int = 0
    blocked_until: float = 0.0
    last_activity: float = 0.0

    def prune(self, now: float) -> None:
        cutoff = now - WINDOW_SECONDS
        while self.timestamps and self.timestamps[0] <= cutoff:
            self.timestamps.popleft()

    def reset_violations_if_expired(self, now: float) -> None:
        if (
            self.violation_level > 0
            and now >= self.blocked_until
            and now - self.last_activity >= VIOLATION_RESET_SECONDS
        ):
            self.violation_level = 0

    def is_blocked(self, now: float) -> bool:
        return now < self.blocked_until

    def allow(self, now: float) -> bool:
        self.reset_violations_if_expired(now)
        self.prune(now)
        self.last_activity = now

        if len(self.timestamps) >= MAX_UPDATES:
            return False

        self.timestamps.append(now)
        return True

    def apply_violation(self, now: float) -> tuple[int, float]:
        self.violation_level += 1
        cooldown_index = min(
            self.violation_level - 1,
            len(COOLDOWN_STAGES) - 1,
        )
        duration = COOLDOWN_STAGES[cooldown_index]
        self.blocked_until = now + duration
        self.last_activity = now
        self.timestamps.clear()
        return self.violation_level, duration

    def is_expired(self, now: float) -> bool:
        return (
            not self.is_blocked(now)
            and now - self.last_activity >= MAX_INACTIVE_SECONDS
        )


class AntiSpamMiddleware(BaseMiddleware):
    """Protect one observer with independent per-user in-memory rate limits."""

    def __init__(self, *, antispam_service: AntiSpamService | None = None) -> None:
        self._states: dict[int, SpamState] = {}
        self._last_cleanup_at = 0.0
        self._antispam_service = antispam_service

    def _cleanup_if_needed(self, now: float) -> None:
        if now - self._last_cleanup_at < CLEANUP_INTERVAL_SECONDS:
            return

        expired_user_ids = [
            user_id
            for user_id, state in self._states.items()
            if state.is_expired(now)
        ]
        for user_id in expired_user_ids:
            del self._states[user_id]

        self._last_cleanup_at = now

    async def _warn(self, event: Message | CallbackQuery, duration: float) -> None:
        text = f"{WARNING_MESSAGE} (محدودیت: {int(duration)} ثانیه)"
        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        else:
            await event.answer(text)

    async def _notify_blocked(self, event: Message | CallbackQuery) -> None:
        if isinstance(event, CallbackQuery):
            await event.answer(BLOCKED_MESSAGE, show_alert=True)
        else:
            await event.answer(BLOCKED_MESSAGE)

    async def _block_user(
        self,
        *,
        user_id: int,
        user_service: UserService,
    ) -> bool:
        if not await user_service.exists(user_id):
            return False

        await user_service.block_user(user_id)

        if self._antispam_service:
            await self._antispam_service.record_block(user_id)

        return True

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        user_id = event.from_user.id
        if user_id in ADMIN_IDS:
            return await handler(event, data)

        if self._antispam_service is None:
            self._antispam_service = data.get("antispam_service")

        now = time.monotonic()
        self._cleanup_if_needed(now)

        state = self._states.setdefault(user_id, SpamState(last_activity=now))

        if state.is_blocked(now):
            state.last_activity = now
            if isinstance(event, CallbackQuery):
                await event.answer()
            return None

        if not state.allow(now):
            violation_level, duration = state.apply_violation(now)

            if self._antispam_service:
                await self._antispam_service.record_warning(user_id)

            if violation_level >= MAX_SPAM_VIOLATIONS:
                user_service: UserService = data["user_service"]
                was_blocked = await self._block_user(
                    user_id=user_id,
                    user_service=user_service,
                )
                self._states.pop(user_id, None)

                if was_blocked:
                    await self._notify_blocked(event)
                else:
                    await self._warn(event, duration)
                return None

            await self._warn(event, duration)
            return None

        return await handler(event, data)
