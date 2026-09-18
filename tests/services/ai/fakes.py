from contextlib import asynccontextmanager
from datetime import datetime

from models.ai import AIProviderConfig, AIProviderKind, AIReport
from services.ai.provider import AIRequest, AIResponse


class FakeProviderRepository:
    def __init__(self, configs: list[AIProviderConfig]) -> None:
        self.configs = {config.key: config for config in configs}

    async def list_all(self) -> list[AIProviderConfig]:
        return sorted(self.configs.values(), key=lambda c: (c.priority, c.key))

    async def get(self, key: str) -> AIProviderConfig | None:
        return self.configs.get(key)

    async def upsert(self, provider: AIProviderConfig) -> AIProviderConfig:
        self.configs[provider.key] = provider
        return provider

    async def delete(self, key: str) -> bool:
        return self.configs.pop(key, None) is not None

    def scope(self):
        @asynccontextmanager
        async def _scope():
            yield self

        return _scope


class FakeReportRepository:
    def __init__(self) -> None:
        self.reports: list[AIReport] = []

    async def create(self, report: AIReport) -> AIReport:
        report.id = len(self.reports) + 1
        self.reports.append(report)
        return report

    async def list_recent(self, *, offset: int, limit: int) -> list[AIReport]:
        return list(reversed(self.reports))[offset : offset + limit]

    async def count(self) -> int:
        return len(self.reports)

    async def get_latest(self, kind: str | None = None) -> AIReport | None:
        for report in reversed(self.reports):
            if kind is None or report.kind.value == kind:
                return report
        return None

    async def sum_tokens_since(self, since: datetime) -> tuple[int, int]:
        rows = [r for r in self.reports if r.created_at >= since]
        return sum(r.tokens_in for r in rows), sum(r.tokens_out for r in rows)


class ScriptedProvider:
    """Returns/raises whatever is queued, in order; records requests."""

    def __init__(self, key: str, outcomes: list[AIResponse | Exception]) -> None:
        self.key = key
        self.outcomes = list(outcomes)
        self.requests: list[AIRequest] = []

    async def complete(self, request: AIRequest) -> AIResponse:
        self.requests.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def config(key: str, priority: int, **overrides) -> AIProviderConfig:
    base = dict(
        key=key,
        display_name=key.title(),
        kind=AIProviderKind.OPENAI_COMPATIBLE,
        base_url="https://example/v1",
        model="m",
        api_key_env=f"{key.upper()}_API_KEY",
        priority=priority,
    )
    base.update(overrides)
    return AIProviderConfig(**base)
