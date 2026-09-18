from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from core.timezone import tehran_now


class AIProviderKind(str, Enum):
    """API *shape*, not vendor. One adapter per kind."""

    OPENAI_COMPATIBLE = "openai_compatible"
    GEMINI = "gemini"


class AIProviderStatus(str, Enum):
    READY = "ready"
    COOLDOWN = "cooldown"  # quota hit; retry after cooldown_until
    FAILED = "failed"  # auth error or repeated failures; needs admin attention


@dataclass(slots=True)
class AIProviderConfig:
    """One configured model. The API key itself is never stored: only the
    name of the environment variable holding it (``api_key_env``)."""

    key: str
    display_name: str
    kind: AIProviderKind
    base_url: str
    model: str
    api_key_env: str
    enabled: bool = True
    priority: int = 100  # lower runs first
    status: AIProviderStatus = AIProviderStatus.READY
    cooldown_until: datetime | None = None
    daily_token_budget: int | None = None
    tokens_in_total: int = 0
    tokens_out_total: int = 0
    tokens_today: int = 0
    tokens_today_date: str | None = None  # "YYYY-MM-DD" Tehran day
    last_error: str | None = None
    last_used_at: datetime | None = None
    created_at: datetime = field(default_factory=tehran_now)
    updated_at: datetime = field(default_factory=tehran_now)

    @property
    def tokens_total(self) -> int:
        return self.tokens_in_total + self.tokens_out_total


class AIReportKind(str, Enum):
    ANOMALY = "anomaly"  # triggered by rule anomalies
    DIGEST = "digest"  # scheduled periodic summary
    MANUAL = "manual"  # admin pressed "analyse now"


@dataclass(slots=True)
class AIReport:
    id: int | None
    kind: AIReportKind
    provider_key: str
    severity: str  # "info" | "warning" | "critical"
    summary: str  # model output (Persian, short)
    anomaly_keys: str  # comma-separated rule keys that triggered it
    tokens_in: int
    tokens_out: int
    created_at: datetime = field(default_factory=tehran_now)
