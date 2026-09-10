from dataclasses import dataclass, field
from datetime import datetime

from core.timezone import tehran_now

DEFAULT_OFFLINE_MESSAGE = "⛔️ ربات در حال حاضر غیرفعال است. لطفاً بعداً دوباره تلاش کنید."
DEFAULT_MAINTENANCE_MESSAGE = "🛠 ربات در حال بروزرسانی و نگهداری است. لطفاً کمی بعد دوباره تلاش کنید."
# Referral reward: the referrer earns ``coins`` every time the number of their
# *registered* referrals reaches a multiple of ``per_invites``.
DEFAULT_REFERRAL_REWARD_COINS = 1
DEFAULT_REFERRAL_REWARD_PER_INVITES = 1


@dataclass
class BotSettings:
    id: int = 1
    bot_enabled: bool = True
    maintenance_mode: bool = False
    antispam_enabled: bool = True
    force_subscription_enabled: bool = False
    offline_message: str = DEFAULT_OFFLINE_MESSAGE
    maintenance_message: str = DEFAULT_MAINTENANCE_MESSAGE
    referral_reward_coins: int = DEFAULT_REFERRAL_REWARD_COINS
    referral_reward_per_invites: int = DEFAULT_REFERRAL_REWARD_PER_INVITES
    updated_at: datetime = field(default_factory=tehran_now)
