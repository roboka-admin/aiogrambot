"""Background health monitoring.

Phase 1 is rule-based only: collect a compact snapshot, evaluate thresholds,
and alert admins. The same snapshot is the input for the AI analysis layer
added in later phases.
"""

from services.monitoring.service import MonitoringService
from services.monitoring.snapshot import MonitoringSnapshot

__all__ = ["MonitoringService", "MonitoringSnapshot"]
