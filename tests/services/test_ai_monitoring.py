from datetime import timedelta

import pytest

from core.timezone import tehran_now
from models.ai import AIProviderStatus, AIReport, AIReportKind
from services.ai.provider import AIAuthError, AIProviderError, AIQuotaError, AIResponse
from services.ai_monitoring import REPORTS_PAGE_SIZE, AIMonitoringService
from tests.services.ai.fakes import (
    FakeProviderRepository,
    FakeReportRepository,
    ScriptedProvider,
    config,
)


def make_service(configs, *, secrets=None, provider=None, reports=None):
    provider_repo = FakeProviderRepository(configs)
    report_repo = FakeReportRepository()
    for report in reports or []:
        report_repo.reports.append(report)
    secrets = secrets or {}
    service = AIMonitoringService(
        provider_repository=provider_repo,
        report_repository=report_repo,
        secret_resolver=secrets.get,
        provider_builder=(lambda _config: provider) if provider is not None else None,
    )
    return service, provider_repo, report_repo


def report(**overrides) -> AIReport:
    base = dict(
        id=None,
        kind=AIReportKind.DIGEST,
        provider_key="gemini",
        severity="info",
        summary="ok",
        anomaly_keys="",
        tokens_in=100,
        tokens_out=50,
    )
    base.update(overrides)
    return AIReport(**base)


async def test_list_providers_reports_effective_status():
    service, _, _ = make_service(
        [
            config("gemini", 10, api_key_env="G"),
            config("mistral", 20, api_key_env="M", enabled=False),
            config("nokey", 30, api_key_env="NOPE"),
            config("cool", 40, api_key_env="G", status=AIProviderStatus.COOLDOWN),
        ],
        secrets={"G": "k", "M": "k"},
    )
    views = await service.list_providers()
    assert [v.effective_status for v in views] == ["ready", "disabled", "no_key", "cooldown"]


async def test_tokens_today_ignores_counter_from_previous_day():
    today = tehran_now().strftime("%Y-%m-%d")
    service, _, _ = make_service(
        [
            config("a", 10, api_key_env="G", tokens_today=40, tokens_today_date=today),
            config("b", 20, api_key_env="G", tokens_today=99, tokens_today_date="2000-01-01"),
        ],
        secrets={"G": "k"},
    )
    views = await service.list_providers()
    assert [v.tokens_today for v in views] == [40, 0]


async def test_toggle_and_reset_provider():
    service, repo, _ = make_service(
        [
            config(
                "gemini",
                10,
                api_key_env="G",
                status=AIProviderStatus.FAILED,
                last_error="401",
                cooldown_until=tehran_now(),
            )
        ],
        secrets={"G": "k"},
    )
    view = await service.toggle_provider("gemini")
    assert view.config.enabled is False
    assert view.effective_status == "disabled"

    view = await service.reset_provider("gemini")
    assert repo.configs["gemini"].status is AIProviderStatus.READY
    assert repo.configs["gemini"].last_error is None
    assert repo.configs["gemini"].cooldown_until is None
    assert view.effective_status == "disabled"  # still disabled; reset only clears errors


async def test_make_primary_moves_provider_ahead_of_all_others():
    service, repo, _ = make_service(
        [config("gemini", 10, api_key_env="G"), config("mistral", 20, api_key_env="G")],
        secrets={"G": "k"},
    )
    await service.make_primary("mistral")
    ordered = [c.key for c in await repo.list_all()]
    assert ordered == ["mistral", "gemini"]
    assert repo.configs["mistral"].priority < repo.configs["gemini"].priority


async def test_unknown_provider_raises_key_error():
    service, _, _ = make_service([config("gemini", 10, api_key_env="G")])
    with pytest.raises(KeyError):
        await service.toggle_provider("nope")
    with pytest.raises(KeyError):
        await service.make_primary("nope")


async def test_set_model_validates_input_without_touching_provider():
    provider = ScriptedProvider("gemini", [])
    service, repo, _ = make_service(
        [config("gemini", 10, api_key_env="G", model="old")], secrets={"G": "k"}, provider=provider
    )
    with pytest.raises(ValueError):
        await service.set_model("gemini", "")
    with pytest.raises(ValueError):
        await service.set_model("gemini", "two words")
    assert repo.configs["gemini"].model == "old"
    assert provider.requests == []


async def test_set_model_saves_then_verifies_success():
    provider = ScriptedProvider("gemini", [AIResponse(text="OK", tokens_in=7, tokens_out=1)])
    service, repo, _ = make_service(
        [config("gemini", 10, api_key_env="G", status=AIProviderStatus.FAILED, last_error="404")],
        secrets={"G": "k"},
        provider=provider,
    )
    view, result = await service.set_model("gemini", "  gemini-3.5-flash-lite ")
    assert result.ok is True
    assert view.config.model == "gemini-3.5-flash-lite"
    assert view.effective_status == "ready"
    assert repo.configs["gemini"].last_error is None
    assert len(provider.requests) == 1


async def test_set_model_with_unknown_model_is_saved_but_marked_failed():
    provider = ScriptedProvider("gemini", [AIProviderError("HTTP 404: model not found")])
    service, repo, _ = make_service(
        [config("gemini", 10, api_key_env="G")], secrets={"G": "k"}, provider=provider
    )
    view, result = await service.set_model("gemini", "gemini-9-does-not-exist")
    assert result.ok is False
    assert repo.configs["gemini"].model == "gemini-9-does-not-exist"  # saved so admin can see/fix
    assert view.effective_status == "failed"
    assert "404" in (repo.configs["gemini"].last_error or "")


async def test_test_provider_success_marks_ready_and_counts_tokens():
    provider = ScriptedProvider("gemini", [AIResponse(text="OK", tokens_in=7, tokens_out=1)])
    service, repo, _ = make_service(
        [config("gemini", 10, api_key_env="G", status=AIProviderStatus.COOLDOWN, last_error="429")],
        secrets={"G": "k"},
        provider=provider,
    )
    result = await service.test_provider("gemini")
    assert result.ok is True
    assert result.detail == "OK"
    assert result.tokens == 8
    stored = repo.configs["gemini"]
    assert stored.status is AIProviderStatus.READY
    assert stored.last_error is None
    assert stored.tokens_in_total == 7 and stored.tokens_out_total == 1
    assert stored.last_used_at is not None
    assert provider.requests[0].max_tokens <= 10


async def test_test_provider_auth_error_marks_failed():
    provider = ScriptedProvider("gemini", [AIAuthError("gemini: 401 invalid key")])
    service, repo, _ = make_service(
        [config("gemini", 10, api_key_env="G")], secrets={"G": "k"}, provider=provider
    )
    result = await service.test_provider("gemini")
    assert result.ok is False
    assert "401" in result.detail
    assert repo.configs["gemini"].last_error == "gemini: 401 invalid key"
    assert repo.configs["gemini"].status is AIProviderStatus.FAILED


async def test_test_provider_generic_error_marks_failed_too():
    provider = ScriptedProvider("gemini", [AIProviderError("HTTP 404: model not found")])
    service, repo, _ = make_service(
        [config("gemini", 10, api_key_env="G")], secrets={"G": "k"}, provider=provider
    )
    result = await service.test_provider("gemini")
    assert result.ok is False
    assert repo.configs["gemini"].status is AIProviderStatus.FAILED
    assert repo.configs["gemini"].cooldown_until is None


async def test_test_provider_quota_error_marks_cooldown():
    provider = ScriptedProvider("gemini", [AIQuotaError("429 quota")])
    service, repo, _ = make_service(
        [config("gemini", 10, api_key_env="G")], secrets={"G": "k"}, provider=provider
    )
    before = tehran_now()
    result = await service.test_provider("gemini")
    assert result.ok is False
    stored = repo.configs["gemini"]
    assert stored.status is AIProviderStatus.COOLDOWN
    assert stored.cooldown_until is not None and stored.cooldown_until > before


async def test_test_provider_without_api_key_explains_missing_env():
    service, _, _ = make_service([config("gemini", 10, api_key_env="GEMINI_API_KEY")])
    result = await service.test_provider("gemini")
    assert result.ok is False
    assert "GEMINI_API_KEY" in result.detail


async def test_reports_page_clamps_and_paginates_newest_first():
    reports = [report(summary=f"r{i}") for i in range(REPORTS_PAGE_SIZE * 2 + 1)]
    service, _, _ = make_service([], reports=reports)

    first = await service.get_reports_page(0)
    assert first.total == REPORTS_PAGE_SIZE * 2 + 1
    assert first.total_pages == 3
    assert [r.summary for r in first.reports][0] == f"r{REPORTS_PAGE_SIZE * 2}"

    last = await service.get_reports_page(99)
    assert last.page == 2
    assert len(last.reports) == 1

    negative = await service.get_reports_page(-5)
    assert negative.page == 0


async def test_reports_page_when_empty():
    service, _, _ = make_service([])
    page = await service.get_reports_page(0)
    assert page.reports == [] and page.total_pages == 1 and page.page == 0


async def test_token_usage_splits_today_and_week():
    now = tehran_now()
    reports = [
        report(tokens_in=10, tokens_out=5, created_at=now),
        report(tokens_in=100, tokens_out=50, created_at=now - timedelta(days=3)),
        report(tokens_in=1000, tokens_out=500, created_at=now - timedelta(days=30)),
    ]
    service, _, _ = make_service([], reports=reports)
    usage = await service.get_token_usage()
    assert (usage.today_in, usage.today_out) == (10, 5)
    assert (usage.last_7_days_in, usage.last_7_days_out) == (110, 55)
