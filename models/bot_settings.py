from dataclasses import dataclass, field
from datetime import datetime

from core.timezone import tehran_now


DEFAULT_OFFLINE_MESSAGE = "⛔️ ربات در حال حاضر غیرفعال است. لطفاً بعداً دوباره تلاش کنید."
DEFAULT_MAINTENANCE_MESSAGE = "🛠 ربات در حال بروزرسانی و نگهداری است. لطفاً کمی بعد دوباره تلاش کنید."


@dataclass
class BotSettings:
    id: int = 1
    bot_enabled: bool = True
    maintenance_mode: bool = False
    offline_message: str = DEFAULT_OFFLINE_MESSAGE
    maintenance_message: str = DEFAULT_MAINTENANCE_MESSAGE
    updated_at: datetime = field(default_factory=tehran_now)
