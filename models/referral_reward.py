from dataclasses import dataclass, field
from datetime import datetime

from core.timezone import tehran_now


@dataclass(slots=True)
class ReferralRewardEntry:
    """One ledger row: coins credited to a referrer for a batch of invites.

    ``invites_consumed`` is how many registered referrals this payout
    "used up", so future threshold checks only look at invites that have
    not been rewarded yet — regardless of later changes to the settings.
    ``triggered_by_user_id`` is the referred user whose registration
    tipped the threshold (for auditing).
    """

    id: int | None
    referrer_id: int
    triggered_by_user_id: int
    coins: int
    invites_consumed: int
    created_at: datetime = field(default_factory=tehran_now)
