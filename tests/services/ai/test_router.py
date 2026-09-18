from datetime import timedelta

import pytest

from core.timezone import tehran_now
from models.ai import AIProviderStatus
from services.ai import AIRouter, NoProviderAvailable
from services.ai.provider import AIAuthError, AIProviderError, AIQuotaError, AIRequest, AIResponse
from tests.services.ai.fakes import FakeProviderRepository, ScriptedProvider, config

REQ = AIRequest(system="s", user="u")
OK = AIResponse(text="fine", tokens_in=10, tokens_out=5)


def make_router(repo: FakeProviderRepository, providers: dict[str, ScriptedProvider | None]):
    return AIRouter(
        repository_factory=repo.scope(),
        provider_builder=lambda cfg: providers.get(cfg.key),
        quota_cooldown=timedelta(hours=1),
    )


@pytest.mark.asyncio
async def test_uses_highest_priority_provider_and_records_usage():
    repo = FakeProviderRepository([config("gemini", 10), config("mistral", 20)])
    gemini = ScriptedProvider("gemini", [OK])
    mistral = ScriptedProvider("mistral", [OK])

    result = await make_router(repo, {"gemini": gemini, "mistral": mistral}).complete(REQ)

    assert result.provider_key == "gemini"
    assert result.switched_from is None
    assert mistral.requests == []
    stored = repo.configs["gemini"]
    assert (stored.tokens_in_total, stored.tokens_out_total, stored.tokens_today) == (10, 5, 15)
    assert stored.tokens_today_date == tehran_now().strftime("%Y-%m-%d")
    assert stored.last_used_at is not None


@pytest.mark.asyncio
async def test_quota_error_cools_down_and_fails_over():
    repo = FakeProviderRepository([config("gemini", 10), config("mistral", 20)])
    gemini = ScriptedProvider("gemini", [AIQuotaError("429")])
    mistral = ScriptedProvider("mistral", [OK])
    router = make_router(repo, {"gemini": gemini, "mistral": mistral})

    result = await router.complete(REQ)

    assert result.provider_key == "mistral"
    assert result.switched_from == "gemini"
    cooled = repo.configs["gemini"]
    assert cooled.status is AIProviderStatus.COOLDOWN
    assert cooled.cooldown_until is not None and cooled.cooldown_until > tehran_now()
    assert cooled.last_error == "429"

    # While cooling down gemini is not even tried.
    mistral.outcomes.append(OK)
    second = await router.complete(REQ)
    assert second.provider_key == "mistral"
    assert second.switched_from is None
    assert len(gemini.requests) == 1


@pytest.mark.asyncio
async def test_cooldown_expiry_restores_provider():
    expired = config("gemini", 10, status=AIProviderStatus.COOLDOWN,
                     cooldown_until=tehran_now() - timedelta(minutes=1))
    repo = FakeProviderRepository([expired, config("mistral", 20)])
    gemini = ScriptedProvider("gemini", [OK])

    result = await make_router(repo, {"gemini": gemini}).complete(REQ)

    assert result.provider_key == "gemini"
    assert repo.configs["gemini"].status is AIProviderStatus.READY
    assert repo.configs["gemini"].cooldown_until is None


@pytest.mark.asyncio
async def test_auth_error_marks_failed_permanently():
    repo = FakeProviderRepository([config("gemini", 10), config("mistral", 20)])
    gemini = ScriptedProvider("gemini", [AIAuthError("bad key")])
    mistral = ScriptedProvider("mistral", [OK, OK])
    router = make_router(repo, {"gemini": gemini, "mistral": mistral})

    await router.complete(REQ)
    await router.complete(REQ)

    assert repo.configs["gemini"].status is AIProviderStatus.FAILED
    assert len(gemini.requests) == 1


@pytest.mark.asyncio
async def test_generic_error_records_message_but_keeps_provider_ready():
    repo = FakeProviderRepository([config("gemini", 10), config("mistral", 20)])
    gemini = ScriptedProvider("gemini", [AIProviderError("HTTP 500"), OK])
    mistral = ScriptedProvider("mistral", [OK])
    router = make_router(repo, {"gemini": gemini, "mistral": mistral})

    first = await router.complete(REQ)
    assert first.provider_key == "mistral"
    assert repo.configs["gemini"].status is AIProviderStatus.READY
    assert repo.configs["gemini"].last_error == "HTTP 500"

    second = await router.complete(REQ)
    assert second.provider_key == "gemini"
    assert repo.configs["gemini"].last_error is None


@pytest.mark.asyncio
async def test_skips_disabled_budget_exhausted_and_keyless_providers():
    today = tehran_now().strftime("%Y-%m-%d")
    repo = FakeProviderRepository([
        config("off", 1, enabled=False),
        config("broke", 2, daily_token_budget=100, tokens_today=100, tokens_today_date=today),
        config("nokey", 3),
        config("mistral", 4),
    ])
    providers = {
        "off": ScriptedProvider("off", [OK]),
        "broke": ScriptedProvider("broke", [OK]),
        "nokey": None,
        "mistral": ScriptedProvider("mistral", [OK]),
    }

    result = await make_router(repo, providers).complete(REQ)

    assert result.provider_key == "mistral"
    # "nokey" was skipped silently, so no switch is reported
    assert result.switched_from is None
    assert providers["off"].requests == [] and providers["broke"].requests == []


@pytest.mark.asyncio
async def test_budget_resets_on_a_new_day():
    repo = FakeProviderRepository([
        config("gemini", 10, daily_token_budget=100, tokens_today=100, tokens_today_date="2000-01-01"),
    ])
    gemini = ScriptedProvider("gemini", [OK])

    result = await make_router(repo, {"gemini": gemini}).complete(REQ)

    assert result.provider_key == "gemini"
    assert repo.configs["gemini"].tokens_today == 15


@pytest.mark.asyncio
async def test_raises_when_everything_fails():
    repo = FakeProviderRepository([config("gemini", 10), config("mistral", 20)])
    providers = {
        "gemini": ScriptedProvider("gemini", [AIQuotaError("429")]),
        "mistral": ScriptedProvider("mistral", [AIProviderError("down")]),
    }
    with pytest.raises(NoProviderAvailable, match="down"):
        await make_router(repo, providers).complete(REQ)


@pytest.mark.asyncio
async def test_raises_when_no_candidates():
    repo = FakeProviderRepository([config("gemini", 10, enabled=False)])
    with pytest.raises(NoProviderAvailable):
        await make_router(repo, {}).complete(REQ)
