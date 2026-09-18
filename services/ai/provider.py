from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class AIProviderError(Exception):
    """The provider could not complete the request (network, 5xx, bad payload)."""


class AIQuotaError(AIProviderError):
    """Rate limit or quota exhausted (HTTP 429 / RESOURCE_EXHAUSTED)."""


class AIAuthError(AIProviderError):
    """Invalid or missing credentials (HTTP 401/403)."""


@dataclass(frozen=True, slots=True)
class AIRequest:
    system: str
    user: str
    max_tokens: int = 350
    temperature: float = 0.2


@dataclass(frozen=True, slots=True)
class AIResponse:
    text: str
    tokens_in: int
    tokens_out: int

    @property
    def tokens_total(self) -> int:
        return self.tokens_in + self.tokens_out


class AIProvider(Protocol):
    """Minimal contract every adapter fulfils: one prompt in, one text out."""

    key: str

    async def complete(self, request: AIRequest) -> AIResponse: ...
