"""AI provider abstraction used by the monitoring analysis layer.

- ``provider.py``   : request/response types, error taxonomy, ``AIProvider`` Protocol
- ``adapters/``     : one small HTTP adapter per API *shape* (not per vendor)
- ``registry.py``   : build an adapter from a stored ``AIProviderConfig``
- ``router.py``     : pick the active provider, fail over on quota/errors,
                      persist usage and cooldowns
"""

from services.ai.provider import AIProvider, AIRequest, AIResponse
from services.ai.router import AIRouter, AIRouterResult, NoProviderAvailable

__all__ = [
    "AIProvider",
    "AIRequest",
    "AIResponse",
    "AIRouter",
    "AIRouterResult",
    "NoProviderAvailable",
]
