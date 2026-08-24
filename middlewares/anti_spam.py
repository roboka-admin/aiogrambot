"""
Anti-Spam Middleware for aiogram 3.x

Provides temporary flood protection for messages and callback queries.
Tracks violations per user and applies escalating cooldowns.
Admins are exempt from anti-spam protection.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, User as TelegramUser

from config import ADMIN_IDS


# ============================================================
# Configuration constants - adjust these to tune behavior
# ============================================================

# Sliding window limits
MAX_UPDATES: int = 5          # Maximum updates allowed in the window
WINDOW_SECONDS: float = 3.0   # Time window in seconds

# Escalating cooldown durations (in seconds)
COOLDOWN_STAGES: tuple[float, ...] = (3.0, 10.0, 30.0, 120.0)

# Violation reset: if user behaves normally for this duration,
# their violation level resets to 0
VIOLATION_RESET_SECONDS: float = 60.0

# Warning message shown when a new cooldown starts
WARNING_MESSAGE: str = "⚠️ لطفاً کمی آهسته‌تر عمل کنید و چند لحظه صبر کنید."

# Maximum age of inactive user tracking data before cleanup (seconds)
MAX_INACTIVE_SECONDS: float = 300.0  # 5 minutes


# ============================================================
# Internal state structures
# ============================================================

@dataclass(slots=True)
class SpamTracker:
    """Tracks recent timestamps for sliding window calculation."""
    timestamps: list[float] = field(default_factory=list)

    def add(self, now: float) -> None:
        """Add a new timestamp."""
        self.timestamps.append(now)

    def prune(self, now: float, window: float) -> None:
        """Remove timestamps outside the sliding window."""
        cutoff = now - window
        # Keep only timestamps within the window
        self.timestamps = [ts for ts in self.timestamps if ts > cutoff]

    def count(self) -> int:
        """Return current count within window."""
        return len(self.timestamps)

    def is_expired(self, now: float, max_inactive: float) -> bool:
        """Check if tracker has no recent activity."""
        if not self.timestamps:
            return True
        return (now - self.timestamps[-1]) > max_inactive


@dataclass(slots=True)
class UserSpamState:
    """Complete spam tracking state for a single user."""
    messages: SpamTracker = field(default_factory=SpamTracker)
    callbacks: SpamTracker = field(default_factory=SpamTracker)
    violation_level: int = 0
    blocked_until: float = 0.0
    last_warning_at: float = 0.0
    last_activity: float = 0.0

    def is_blocked(self, now: float) -> bool:
        """Check if user is currently in cooldown."""
        return now < self.blocked_until

    def remaining_cooldown(self, now: float) -> float:
        """Return remaining cooldown seconds, 0 if not blocked."""
        if self.is_blocked(now):
            return self.blocked_until - now
        return 0.0

    def record_warning_sent(self, now: float) -> None:
        """Mark that a warning has been sent for this cooldown period."""
        self.last_warning_at = now

    def escalate_violation(self) -> None:
        """Increase violation level, capped at maximum stage."""
        if self.violation_level < len(COOLDOWN_STAGES):
            self.violation_level += 1

    def get_cooldown_duration(self) -> float:
        """Get cooldown duration for current violation level (1-indexed)."""
        index = min(self.violation_level - 1, len(COOLDOWN_STAGES) - 1)
        return COOLDOWN_STAGES[index]

    def apply_cooldown(self, now: float) -> float:
        """Apply cooldown based on current violation level, return duration."""
        duration = self.get_cooldown_duration()
        self.blocked_until = now + duration
        return duration

    def maybe_reset_violation(self, now: float) -> None:
        """Reset violation level if user has been well-behaved."""
        if self.violation_level > 0 and (now - self.last_activity) > VIOLATION_RESET_SECONDS:
            self.violation_level = 0
            self.blocked_until = 0.0
            self.last_warning_at = 0.0

    def update_activity(self, now: float) -> None:
        """Update last activity timestamp."""
        self.last_activity = now

    def is_expired(self, now: float, max_inactive: float) -> bool:
        """Check if this user's state can be cleaned up."""
        return (
            self.messages.is_expired(now, max_inactive)
            and self.callbacks.is_expired(now, max_inactive)
            and not self.is_blocked(now)
            and (now - self.last_activity) > max_inactive
        )


class AntiSpamMiddleware(BaseMiddleware):
    """
    Middleware that protects against message and callback spam.

    Features:
    - Separate sliding window tracking for messages vs callbacks
    - Escalating cooldowns on repeated violations
    - Single warning per cooldown period
    - Automatic violation level reset after good behavior
    - Admin exemption
    - In-memory storage with lazy cleanup
    """

    def __init__(self) -> None:
        # user_id -> UserSpamState
        self._user_states: Dict[int, UserSpamState] = {}

    def _get_user_id(self, event: TelegramObject) -> int | None:
        """Extract user ID from event."""
        user: TelegramUser | None = getattr(event, "from_user", None)
        return user.id if user is not None else None

    def _is_admin(self, user_id: int | None) -> bool:
        """Check if user is an admin (exempt from anti-spam)."""
        return user_id is not None and user_id in ADMIN_IDS

    def _get_state(self, user_id: int) -> UserSpamState:
        """Get or create spam state for a user."""
        if user_id not in self._user_states:
            self._user_states[user_id] = UserSpamState()
        return self._user_states[user_id]

    def _cleanup_expired(self, now: float) -> None:
        """Remove expired user states to prevent memory growth."""
        expired_keys = [
            uid for uid, state in self._user_states.items()
            if state.is_expired(now, MAX_INACTIVE_SECONDS)
        ]
        for uid in expired_keys:
            del self._user_states[uid]

    async def _handle_spam_violation(
        self,
        event: TelegramObject,
        state: UserSpamState,
        now: float,
        is_callback: bool,
    ) -> None:
        """
        Handle a spam violation: escalate, apply cooldown, send warning if needed.
        """
        state.escalate_violation()
        cooldown_duration = state.apply_cooldown(now)
        state.record_warning_sent(now)

        # Send single warning for this cooldown period
        warning_text = f"{WARNING_MESSAGE} (محدودیت: {int(cooldown_duration)} ثانیه)"

        if is_callback:
            # For callbacks, use answer() to dismiss loading state
            if isinstance(event, CallbackQuery):
                await event.answer(warning_text, show_alert=True)
        else:
            # For messages, reply normally
            if isinstance(event, Message):
                await event.answer(warning_text)

    def _check_and_update_tracker(
        self,
        tracker: SpamTracker,
        now: float,
        window: float,
        max_updates: int,
    ) -> bool:
        """
        Check if tracker exceeds limit, prune old entries, add current.
        Returns True if within limits, False if spam detected.
        """
        tracker.prune(now, window)
        if tracker.count() >= max_updates:
            return False
        tracker.add(now)
        return True

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        now = time.monotonic()

        # Lazy cleanup of expired states
        self._cleanup_expired(now)

        user_id = self._get_user_id(event)

        # Skip anti-spam for admins or events without user
        if user_id is None or self._is_admin(user_id):
            return await handler(event, data)

        state = self._get_state(user_id)
        state.maybe_reset_violation(now)
        state.update_activity(now)

        # Check if user is currently in cooldown
        if state.is_blocked(now):
            # Silently ignore - no warning, no processing
            if isinstance(event, CallbackQuery):
                # Still need to answer callback to dismiss loading state
                await event.answer()
            return None

        # Determine update type and check limits
        is_callback = isinstance(event, CallbackQuery)
        tracker = state.callbacks if is_callback else state.messages

        # Check sliding window limit
        if not self._check_and_update_tracker(
            tracker, now, WINDOW_SECONDS, MAX_UPDATES
        ):
            # Spam detected - handle violation
            await self._handle_spam_violation(event, state, now, is_callback)
            return None

        # Within limits - proceed to handler
        return await handler(event, data)