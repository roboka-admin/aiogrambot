"""Admin-facing operations for the AI monitoring panel.

Request-scoped like the other services (shares the session/transaction of
the current update). It never calls a model itself except for the explicit
"test connection" action; scheduled analysis lives in
``services.monitoring``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from math import ceil

from core.timezone import tehran_now
from core.transaction import NullTransactionManager, TransactionManager, transactional
from models.ai import AIProviderConfig, AIProviderStatus, AIReport
from repositories.interfaces.ai import IAIProviderRepository, IAIReportRepository
from services.ai.provider import (
    AIAuthError,
    AIProvider,
    AIProviderError,
    AIQuotaError,
    AIRequest,
)
from services.ai.registry import SecretResolver, build_provider, resolve_secret_from_env

ProviderBuilder = Callable[[AIProviderConfig], AIProvider | None]

REPORTS_PAGE_SIZE = 5
TEST_QUOTA_COOLDOWN = timedelta(hours=1)

_TEST_REQUEST = AIRequest(
    system="Reply with exactly one word: OK",
    user="ping",
    max_tokens=5,
    temperature=0.0,
)


@dataclass(frozen=True, slots=True)
class ProviderView:
    config: AIProviderConfig
    has_api_key: bool
    tokens_today: int  # 0 when the stored counter belongs to an earlier day

    @property
    def effective_status(self) -> str:
        """What the router would do with this provider right now."""
        if not self.config.enabled:
            return "disabled"
        if not self.has_api_key:
            return "no_key"
        if self.config.status is AIProviderStatus.FAILED:
            return "failed"
        if self.config.status is AIProviderStatus.COOLDOWN:
            return "cooldown"
        return "ready"


@dataclass(frozen=True, slots=True)
class ReportsPage:
    reports: list[AIReport]
    page: int
    total_pages: int
    total: int


@dataclass(frozen=True, slots=True)
class TokenUsage:
    today_in: int
    today_out: int
    last_7_days_in: int
    last_7_days_out: int


@dataclass(frozen=True, slots=True)
class ConnectionTestResult:
    ok: bool
    provider_key: str
    detail: str
    tokens: int = 0


class AIMonitoringService:
    def __init__(
        self,
        *,
        provider_repository: IAIProviderRepository,
        report_repository: IAIReportRepository,
        transaction_manager: TransactionManager | None = None,
        secret_resolver: SecretResolver = resolve_secret_from_env,
        provider_builder: ProviderBuilder | None = None,
    ) -> None:
        self._providers = provider_repository
        self._reports = report_repository
        self._transaction_manager = transaction_manager or NullTransactionManager()
        self._resolve_secret = secret_resolver
        self._build = provider_builder or (
            lambda config: build_provider(config, resolve_secret=secret_resolver)
        )

    # -------------------------------------------------------------- providers

    @transactional
    async def list_providers(self) -> list[ProviderView]:
        configs = await self._providers.list_all()
        return [self._view(config) for config in configs]

    @transactional
    async def get_provider(self, key: str) -> ProviderView | None:
        config = await self._providers.get(key)
        return None if config is None else self._view(config)

    @transactional
    async def toggle_provider(self, key: str) -> ProviderView:
        config = await self._require(key)
        config.enabled = not config.enabled
        config.updated_at = tehran_now()
        return self._view(await self._providers.upsert(config))

    @transactional
    async def make_primary(self, key: str) -> ProviderView:
        """Give ``key`` the lowest priority number so the router tries it first."""
        configs = await self._providers.list_all()
        target = next((config for config in configs if config.key == key), None)
        if target is None:
            raise KeyError(key)
        lowest = min((config.priority for config in configs), default=100)
        target.priority = lowest - 1
        target.updated_at = tehran_now()
        return self._view(await self._providers.upsert(target))

    @transactional
    async def reset_provider(self, key: str) -> ProviderView:
        """Clear cooldown/failed state and the recorded error after a fix."""
        config = await self._require(key)
        config.status = AIProviderStatus.READY
        config.cooldown_until = None
        config.last_error = None
        config.updated_at = tehran_now()
        return self._view(await self._providers.upsert(config))

    async def set_model(self, key: str, model: str) -> tuple[ProviderView, ConnectionTestResult]:
        """Save a new model name and immediately verify it.

        The stored status is whatever the verification produced, so the panel
        never shows a freshly typed (possibly wrong) model as "ready".
        """
        model = model.strip()
        if not model or len(model) > 100 or any(ch.isspace() for ch in model):
            raise ValueError("model name must be a single token up to 100 characters")
        async with self._transaction_manager.transaction():
            config = await self._require(key)
            config.model = model
            config.updated_at = tehran_now()
            await self._providers.upsert(config)
        result = await self.test_provider(key)
        view = await self.get_provider(key)
        assert view is not None  # just upserted above
        return view, result

    async def test_provider(self, key: str) -> ConnectionTestResult:
        """One tiny real request; the stored status follows the outcome.

        Mapping mirrors the router (quota -> COOLDOWN, auth -> FAILED) with one
        deliberate difference: a generic error (404 unknown model, 5xx, network)
        also marks FAILED. The router treats those as transient and fails over,
        but an admin-run test is a verification step: an error must be visible
        as the provider's status until the admin fixes it and re-tests/resets.
        """
        async with self._transaction_manager.transaction():
            config = await self._require(key)
        provider = self._build(config)
        if provider is None:
            return ConnectionTestResult(
                ok=False, provider_key=key, detail=f"متغیر محیطی {config.api_key_env} تنظیم نشده است."
            )
        now = tehran_now()
        try:
            response = await provider.complete(_TEST_REQUEST)
        except AIProviderError as exc:
            async with self._transaction_manager.transaction():
                config = await self._require(key)
                if isinstance(exc, AIQuotaError):
                    config.status = AIProviderStatus.COOLDOWN
                    config.cooldown_until = now + TEST_QUOTA_COOLDOWN
                else:
                    config.status = AIProviderStatus.FAILED
                    config.cooldown_until = None
                config.last_error = str(exc)[:500]
                config.updated_at = now
                await self._providers.upsert(config)
            return ConnectionTestResult(ok=False, provider_key=key, detail=str(exc)[:300])

        async with self._transaction_manager.transaction():
            config = await self._require(key)
            config.status = AIProviderStatus.READY
            config.cooldown_until = None
            config.last_error = None
            config.last_used_at = now
            config.tokens_in_total += response.tokens_in
            config.tokens_out_total += response.tokens_out
            config.updated_at = now
            await self._providers.upsert(config)
        return ConnectionTestResult(
            ok=True,
            provider_key=key,
            detail=response.text[:100] or "(پاسخ خالی)",
            tokens=response.tokens_total,
        )

    # ---------------------------------------------------------------- reports

    @transactional
    async def get_reports_page(self, page: int) -> ReportsPage:
        total = await self._reports.count()
        total_pages = max(1, ceil(total / REPORTS_PAGE_SIZE))
        page = min(max(page, 0), total_pages - 1)
        reports = await self._reports.list_recent(
            offset=page * REPORTS_PAGE_SIZE, limit=REPORTS_PAGE_SIZE
        )
        return ReportsPage(reports=reports, page=page, total_pages=total_pages, total=total)

    @transactional
    async def get_latest_report(self) -> AIReport | None:
        return await self._reports.get_latest()

    @transactional
    async def get_token_usage(self) -> TokenUsage:
        now = tehran_now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_in, today_out = await self._reports.sum_tokens_since(today_start)
        week_in, week_out = await self._reports.sum_tokens_since(today_start - timedelta(days=7))
        return TokenUsage(
            today_in=today_in,
            today_out=today_out,
            last_7_days_in=week_in,
            last_7_days_out=week_out,
        )

    # ---------------------------------------------------------------- helpers

    async def _require(self, key: str) -> AIProviderConfig:
        config = await self._providers.get(key)
        if config is None:
            raise KeyError(key)
        return config

    def _view(self, config: AIProviderConfig) -> ProviderView:
        today = tehran_now().strftime("%Y-%m-%d")
        return ProviderView(
            config=config,
            has_api_key=bool(self._resolve_secret(config.api_key_env)),
            tokens_today=config.tokens_today if config.tokens_today_date == today else 0,
        )
