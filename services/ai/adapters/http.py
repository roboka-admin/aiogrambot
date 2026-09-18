"""Shared aiohttp plumbing for adapters: one call, mapped errors."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import aiohttp

from services.ai.provider import AIAuthError, AIProviderError, AIQuotaError

_TIMEOUT = aiohttp.ClientTimeout(total=45)


async def post_json(url: str, *, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    """POST JSON and return the decoded body, translating HTTP failures.

    A fresh session per call is deliberate: the monitor makes a handful of
    requests per day, so connection reuse buys nothing and this avoids
    owning a long-lived session lifecycle.
    """
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.post(url, headers=headers, json=payload) as response:
                body_text = await response.text()
                status = response.status
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        raise AIProviderError(f"request failed: {exc}") from exc

    if status == 429:
        raise AIQuotaError(_short(body_text))
    if status in (401, 403):
        raise AIAuthError(_short(body_text))
    if status >= 400:
        raise AIProviderError(f"HTTP {status}: {_short(body_text)}")

    try:
        data = json.loads(body_text)
    except ValueError as exc:
        raise AIProviderError("response is not JSON") from exc
    if not isinstance(data, dict):
        raise AIProviderError("unexpected response shape")
    return data


def _short(text: str, limit: int = 200) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
