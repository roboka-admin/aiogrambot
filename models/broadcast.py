from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class BroadcastRecord:
    """Persisted record of a completed broadcast."""

    id: int | None
    total_recipients: int
    success_count: int
    failed_count: int
    duration_seconds: int
    created_at: datetime = field(default_factory=datetime.utcnow)
