"""Keys for lifetime counters that survive event-row retention.

Event tables (anti-spam, membership checks, AI reports, closed support
tickets) are pruned after a
retention window; before rows are deleted their count is folded into one of
these counters so "all time" figures in the admin panel stay exact.
"""

ANTISPAM_WARNINGS = "antispam_warnings"
ANTISPAM_BLOCKS = "antispam_blocks"
MEMBERSHIP_EVENTS = "membership_events"
SUPPORT_TICKETS_CLOSED = "support_tickets_closed"


def membership_target_kind(target_chat_id: int) -> str:
    return f"{MEMBERSHIP_EVENTS}:{target_chat_id}"
