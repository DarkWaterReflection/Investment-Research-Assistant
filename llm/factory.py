"""Provider selection from configuration.

The active provider is chosen by Settings.llm_provider / llm_model; a missing
key is a hard, typed error — unlike collectors, analysis cannot degrade to
"no LLM", so we fail loudly at startup rather than mid-job.
"""

from __future__ import annotations

import httpx

from core.config import Settings
from llm.base import BaseLLMProvider, LLMAuthError, LLMError
from llm.providers import AnthropicProvider, GeminiProvider, OpenAIProvider


def build_llm_provider(client: httpx.AsyncClient, settings: Settings) -> BaseLLMProvider:
    provider = settings.llm_provider.strip().lower()
    if provider == "anthropic":
        if settings.anthropic_api_key is None:
            raise LLMAuthError(provider, "ANTHROPIC_API_KEY is not set")
        return AnthropicProvider(
            client, settings.anthropic_api_key.get_secret_value(), settings.llm_model
        )
    if provider == "openai":
        if settings.openai_api_key is None:
            raise LLMAuthError(provider, "OPENAI_API_KEY is not set")
        return OpenAIProvider(
            client, settings.openai_api_key.get_secret_value(), settings.llm_model
        )
    if provider == "gemini":
        if settings.gemini_api_key is None:
            raise LLMAuthError(provider, "GEMINI_API_KEY is not set")
        return GeminiProvider(
            client, settings.gemini_api_key.get_secret_value(), settings.llm_model
        )
    raise LLMError(
        provider or "unset",
        f"unknown llm_provider {settings.llm_provider!r}; expected anthropic | openai | gemini",
    )
