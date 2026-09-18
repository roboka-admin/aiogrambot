"""Adapter for the OpenAI ``/chat/completions`` shape.

Covers Mistral, OpenAI, OpenRouter, Groq, DeepSeek, Together, Ollama, ...
Only ``base_url`` and ``model`` differ between them.
"""

from __future__ import annotations

from services.ai.adapters.http import post_json
from services.ai.provider import AIProviderError, AIRequest, AIResponse


class OpenAICompatibleProvider:
    def __init__(self, *, key: str, base_url: str, model: str, api_key: str) -> None:
        self.key = key
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._model = model
        self._api_key = api_key

    async def complete(self, request: AIRequest) -> AIResponse:
        data = await post_json(
            self._url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            payload={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": request.system},
                    {"role": "user", "content": request.user},
                ],
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
            },
        )
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError(f"unexpected response: {str(data)[:200]}") from exc
        usage = data.get("usage") or {}
        return AIResponse(
            text=(text or "").strip(),
            tokens_in=int(usage.get("prompt_tokens") or 0),
            tokens_out=int(usage.get("completion_tokens") or 0),
        )
