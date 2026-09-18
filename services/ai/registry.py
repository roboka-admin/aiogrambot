"""Build a concrete adapter from a stored provider configuration."""

from __future__ import annotations

import os
from collections.abc import Callable

from models.ai import AIProviderConfig, AIProviderKind
from services.ai.adapters.gemini import GeminiProvider
from services.ai.adapters.openai_compatible import OpenAICompatibleProvider
from services.ai.provider import AIProvider

SecretResolver = Callable[[str], str | None]


def resolve_secret_from_env(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value else None


def build_provider(config: AIProviderConfig, *, resolve_secret: SecretResolver = resolve_secret_from_env) -> AIProvider | None:
    """Return an adapter, or ``None`` when its API key is not configured."""
    api_key = resolve_secret(config.api_key_env)
    if not api_key:
        return None

    if config.kind is AIProviderKind.GEMINI:
        return GeminiProvider(
            key=config.key, base_url=config.base_url, model=config.model, api_key=api_key
        )
    if config.kind is AIProviderKind.OPENAI_COMPATIBLE:
        return OpenAICompatibleProvider(
            key=config.key, base_url=config.base_url, model=config.model, api_key=api_key
        )
    raise ValueError(f"unknown provider kind: {config.kind}")
