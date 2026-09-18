import json
from contextlib import asynccontextmanager
from datetime import timedelta

import pytest

from core.timezone import tehran_now
from models.ai import AIReport, AIReportKind
from models.bot_settings import BotSettings
from services.ai import AIRouter
from services.ai.provider import AIProviderError, AIRequest, AIResponse
from services.monitoring.analysis import AIAnalyzer, build_user_prompt
from services.monitoring.rules import Anomaly, Severity
from tests.services.ai.fakes import FakeProviderRepository, FakeReportRepository, ScriptedProvider, config
from tests.services.monitoring.test_rules import make_snapshot


class FakeSettingsRepository:
    def __init__(self, settings: BotSettings | None = None) -> None:
        self.settings = settings

    async def get(self):
        return self.settings

    async def create(self, settings):
        self.settings = settings
        return settings

    async def update(self, settings):
        self.settings = settings
        return settings


def make_analyzer(outcomes, *, settings: BotSettings | None = None):
    providers = FakeProviderRepository([config("gemini", 10)])
    provider = ScriptedProvider("gemini", outcomes)
    router = AIRouter(repository_factory=providers.scope(), provider_builder=lambda _: provider)
    reports = FakeReportRepository()
    settings_repo = FakeSettingsRepository(settings)

    @asynccontextmanager
    async def scope():
        yield reports, settings_repo

    return AIAnalyzer(router=router, repository_factory=scope), provider, reports


ANOMALY = Anomaly(key="memory", severity=Severity.CRITICAL, title="RAM", detail="95%")


def test_prompt_is_compact_json_with_anomalies_and_issues():
    snapshot = make_snapshot(memory_percent=95, errors=7, updates=100)
    prompt = build_user_prompt(snapshot, [ANOMALY], kind=AIReportKind.ANOMALY)

    instruction, payload = prompt.split("\n", 1)
    data = json.loads(payload)
    assert "Diagnose" in instruction
    assert data["res"]["mem_pct"] == 95
    assert data["act"] == {
        "updates": 100, "errors": 7, "spam_warn": 0, "spam_block": 0,
        "blocked_bot": 0, "blocked_bot_total": 0,
    }
    assert data["anomalies"] == [{"key": "memory", "sev": "critical", "detail": "95%"}]
    assert len(prompt) < 700  # keeps the input side cheap


def test_digest_prompt_uses_digest_instruction():
    prompt = build_user_prompt(make_snapshot(), [], kind=AIReportKind.DIGEST)
    assert prompt.startswith("This is a scheduled periodic digest")


@pytest.mark.asyncio
async def test_analyse_persists_report_with_usage_and_severity():
    analyzer, provider, reports = make_analyzer(
        [AIResponse(text="تشخیص: حافظه پر است", tokens_in=120, tokens_out=40)]
    )

    analysis = await analyzer.analyse(make_snapshot(memory_percent=95), [ANOMALY], kind=AIReportKind.ANOMALY)

    assert analysis is not None
    report = analysis.report
    assert report.id == 1 and reports.reports == [report]
    assert report.kind is AIReportKind.ANOMALY
    assert report.provider_key == "gemini"
    assert report.severity == "critical"
    assert report.anomaly_keys == "memory"
    assert (report.tokens_in, report.tokens_out) == (120, 40)
    assert provider.requests[0].system.startswith("You are the on-call SRE")
    assert provider.requests[0].max_tokens == 350


@pytest.mark.asyncio
async def test_analyse_returns_none_when_no_provider_can_answer():
    analyzer, _, reports = make_analyzer([AIProviderError("down")])

    assert await analyzer.analyse(make_snapshot(), [ANOMALY], kind=AIReportKind.ANOMALY) is None
    assert reports.reports == []


@pytest.mark.asyncio
async def test_is_enabled_follows_settings_and_defaults_to_true():
    analyzer, _, _ = make_analyzer([])
    assert await analyzer.is_enabled() is True
    analyzer, _, _ = make_analyzer([], settings=BotSettings(ai_monitoring_enabled=False))
    assert await analyzer.is_enabled() is False


@pytest.mark.asyncio
async def test_digest_due_respects_interval_and_toggle():
    analyzer, _, reports = make_analyzer([], settings=BotSettings(ai_digest_interval_hours=6))
    now = tehran_now()
    assert await analyzer.digest_due(now) is True  # never sent

    reports.reports.append(AIReport(
        id=1, kind=AIReportKind.DIGEST, provider_key="gemini", severity="info", summary="ok",
        anomaly_keys="", tokens_in=1, tokens_out=1, created_at=now - timedelta(hours=5),
    ))
    assert await analyzer.digest_due(now) is False
    assert await analyzer.digest_due(now + timedelta(hours=2)) is True

    analyzer, _, _ = make_analyzer([], settings=BotSettings(ai_monitoring_enabled=False))
    assert await analyzer.digest_due(now) is False
