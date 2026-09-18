"""Adapter for Google Gemini's native ``generateContent`` REST API."""

from __future__ import annotations

from services.ai.adapters.http import post_json
from services.ai.provider import AIProviderError, AIQuotaError, AIRequest, AIResponse


class GeminiProvider:
    def __init__(self, *, key: str, base_url: str, model: str, api_key: str) -> None:
        self.key = key
        self._url = f"{base_url.rstrip('/')}/models/{model}:generateContent"
        self._api_key = api_key

    async def complete(self, request: AIRequest) -> AIResponse:
        try:
            data = await post_json(
                self._url,
                headers={"x-goog-api-key": self._api_key, "Content-Type": "application/json"},
                payload={
                    "system_instruction": {"parts": [{"text": request.system}]},
                    "contents": [{"role": "user", "parts": [{"text": request.user}]}],
                    "generationConfig": {
                        "maxOutputTokens": request.max_tokens,
                        "temperature": request.temperature,
                    },
                },
            )
        except AIProviderError as exc:
            # Gemini sometimes reports exhausted free quota as 400/403 with
            # RESOURCE_EXHAUSTED in the body; treat it as quota for failover.
            if "RESOURCE_EXHAUSTED" in str(exc) and not isinstance(exc, AIQuotaError):
                raise AIQuotaError(str(exc)) from exc
            raise

        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(part.get("text", "") for part in parts)
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError(f"unexpected response: {str(data)[:200]}") from exc
        usage = data.get("usageMetadata") or {}
        return AIResponse(
            text=text.strip(),
            tokens_in=int(usage.get("promptTokenCount") or 0),
            tokens_out=int(usage.get("candidatesTokenCount") or 0),
        )
