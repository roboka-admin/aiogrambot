"""Choose the active provider and fail over when it cannot serve.

Selection order: enabled providers sorted by ``priority`` (lower first),
skipping those in cooldown, over their daily token budget, or without an
API key in the environment. On ``AIQuotaError`` the provider is put in
cooldown and the next one is tried; on ``AIAuthError`` it is marked
``failed`` (needs a human) and the next one is tried; on other errors the
error is recorded and the next one is tried. Usage counters are persisted
after every successful call so the admin panel can show token spend.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime, timedelta

from core.timezone import tehran_now
from models.ai import AIProviderConfig, AIProviderStatus
from repositories.interfaces.ai import IAIProviderRepository
from services.ai.provider import (
    AIAuthError,
    AIProvider,
    AIProviderError,
    AIQuotaError,
    AIRequest,
    AIResponse,
)
from services.ai.registry import SecretResolver, build_provider, resolve_secret_from_env

logger = logging.getLogger(__name__)

ProviderRepositoryFactory = Callable[[], AbstractAsyncContextManager[IAIProviderRepository]]
ProviderBuilder = Callable[[AIProviderConfig], AIProvider | None]


class NoProviderAvailable(Exception):
    """Every configured provider was skipped or failed for this request."""


@dataclass(frozen=True, slots=True)
class AIRouterResult:
    response: AIResponse
    provider_key: str
    switched_from: str | None  # set when a higher-priority provider failed over


class AIRouter:
    def __init__(
        self,
        *,
        repository_factory: ProviderRepositoryFactory,
        provider_builder: ProviderBuilder | None = None,
        secret_resolver: SecretResolver = resolve_secret_from_env,
        quota_cooldown: timedelta = timedelta(hours=1),
    ) -> None:
        self._repository_factory = repository_factory
        self._build = provider_builder or (
            lambda config: build_provider(config, resolve_secret=secret_resolver)
        )
        self._quota_cooldown = quota_cooldown

    async def complete(self, request: AIRequest) -> AIRouterResult:
        async with self._repository_factory() as repository:
            configs = await repository.list_all()
        now = tehran_now()
        candidates = [config for config in configs if self._is_candidate(config, now)]
        if not candidates:
            raise NoProviderAvailable("no enabled provider with an API key is ready")

        first_tried: str | None = None
        last_error: Exception | None = None
        for config in candidates:
            provider = self._build(config)
            if provider is None:
                continue
            first_tried = first_tried or config.key
            try:
                response = await provider.complete(request)
            except AIQuotaError as exc:
                last_error = exc
                await self._mark(config.key, status=AIProviderStatus.COOLDOWN, error=str(exc), now=now)
                logger.warning("AI provider %s hit quota; cooling down", config.key)
                continue
            except AIAuthError as exc:
                last_error = exc
                await self._mark(config.key, status=AIProviderStatus.FAILED, error=str(exc), now=now)
                logger.error("AI provider %s rejected credentials", config.key)
                continue
            except AIProviderError as exc:
                last_error = exc
                await self._mark(config.key, status=None, error=str(exc), now=now)
                logger.warning("AI provider %s failed: %s", config.key, exc)
                continue

            await self._record_usage(config.key, response, now)
            switched_from = first_tried if first_tried != config.key else None
            return AIRouterResult(response=response, provider_key=config.key, switched_from=switched_from)

        raise NoProviderAvailable(str(last_error) if last_error else "no provider had an API key")

    # ---------------------------------------------------------------- helpers

    def _is_candidate(self, config: AIProviderConfig, now: datetime) -> bool:
        if not config.enabled:
            return False
        if config.status is AIProviderStatus.FAILED:
            return False
        if config.status is AIProviderStatus.COOLDOWN:
            if config.cooldown_until is not None and config.cooldown_until > now:
                return False
        if config.daily_token_budget is not None and config.tokens_today_date == _day(now):
            if config.tokens_today >= config.daily_token_budget:
                return False
        return True

    async def _mark(
        self, key: str, *, status: AIProviderStatus | None, error: str, now: datetime
    ) -> None:
        async with self._repository_factory() as repository:
            config = await repository.get(key)
            if config is None:
                return
            if status is AIProviderStatus.COOLDOWN:
                config.status = AIProviderStatus.COOLDOWN
                config.cooldown_until = now + self._quota_cooldown
            elif status is AIProviderStatus.FAILED:
                config.status = AIProviderStatus.FAILED
            config.last_error = error[:500]
            config.updated_at = now
            await repository.upsert(config)

    async def _record_usage(self, key: str, response: AIResponse, now: datetime) -> None:
        async with self._repository_factory() as repository:
            config = await repository.get(key)
            if config is None:
                return
            today = _day(now)
            if config.tokens_today_date != today:
                config.tokens_today = 0
                config.tokens_today_date = today
            config.tokens_today += response.tokens_total
            config.tokens_in_total += response.tokens_in
            config.tokens_out_total += response.tokens_out
            config.status = AIProviderStatus.READY
            config.cooldown_until = None
            config.last_error = None
            config.last_used_at = now
            config.updated_at = now
            await repository.upsert(config)


def _day(now: datetime) -> str:
    return now.strftime("%Y-%m-%d")
