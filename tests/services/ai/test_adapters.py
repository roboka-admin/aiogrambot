from typing import Any

import pytest

from services.ai.adapters import gemini, openai_compatible
from services.ai.provider import AIProviderError, AIQuotaError, AIRequest

REQUEST = AIRequest(system="sys", user="usr", max_tokens=100, temperature=0.1)


def _capture(monkeypatch: pytest.MonkeyPatch, module, response: dict[str, Any] | Exception):
    calls: list[dict[str, Any]] = []

    async def fake_post_json(url, *, headers, payload):
        calls.append({"url": url, "headers": headers, "payload": payload})
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(module, "post_json", fake_post_json)
    return calls


@pytest.mark.asyncio
async def test_openai_compatible_builds_chat_request_and_parses_usage(monkeypatch):
    calls = _capture(
        monkeypatch,
        openai_compatible,
        {
            "choices": [{"message": {"content": "  تشخیص: سالم  "}}],
            "usage": {"prompt_tokens": 40, "completion_tokens": 12},
        },
    )
    provider = openai_compatible.OpenAICompatibleProvider(
        key="mistral", base_url="https://api.mistral.ai/v1/", model="mistral-small-latest", api_key="k"
    )

    response = await provider.complete(REQUEST)

    assert response.text == "تشخیص: سالم"
    assert (response.tokens_in, response.tokens_out) == (40, 12)
    call = calls[0]
    assert call["url"] == "https://api.mistral.ai/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer k"
    assert call["payload"]["model"] == "mistral-small-latest"
    assert call["payload"]["messages"][0] == {"role": "system", "content": "sys"}
    assert call["payload"]["max_tokens"] == 100


@pytest.mark.asyncio
async def test_openai_compatible_rejects_unexpected_shape(monkeypatch):
    _capture(monkeypatch, openai_compatible, {"error": "nope"})
    provider = openai_compatible.OpenAICompatibleProvider(
        key="x", base_url="https://h/v1", model="m", api_key="k"
    )
    with pytest.raises(AIProviderError):
        await provider.complete(REQUEST)


@pytest.mark.asyncio
async def test_gemini_builds_generate_content_request_and_parses_usage(monkeypatch):
    calls = _capture(
        monkeypatch,
        gemini,
        {
            "candidates": [{"content": {"parts": [{"text": "تشخیص: "}, {"text": "سالم"}]}}],
            "usageMetadata": {"promptTokenCount": 30, "candidatesTokenCount": 8},
        },
    )
    provider = gemini.GeminiProvider(
        key="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        model="gemini-2.5-flash-lite",
        api_key="g",
    )

    response = await provider.complete(REQUEST)

    assert response.text == "تشخیص: سالم"
    assert (response.tokens_in, response.tokens_out) == (30, 8)
    call = calls[0]
    assert call["url"].endswith("/models/gemini-2.5-flash-lite:generateContent")
    assert call["headers"]["x-goog-api-key"] == "g"
    assert call["payload"]["system_instruction"] == {"parts": [{"text": "sys"}]}
    assert call["payload"]["generationConfig"]["maxOutputTokens"] == 100


@pytest.mark.asyncio
async def test_gemini_maps_resource_exhausted_to_quota_error(monkeypatch):
    _capture(monkeypatch, gemini, AIProviderError("HTTP 403: RESOURCE_EXHAUSTED quota"))
    provider = gemini.GeminiProvider(key="g", base_url="https://h", model="m", api_key="k")
    with pytest.raises(AIQuotaError):
        await provider.complete(REQUEST)
