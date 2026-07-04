import pytest

from core.config import Settings
from llm.base import LLMAuthError, LLMError
from llm.factory import build_llm_provider
from llm.providers import AnthropicProvider, GeminiProvider, OpenAIProvider


def make_settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


async def test_builds_provider_matching_settings(http_client):
    cases = [
        ("anthropic", {"anthropic_api_key": "ak"}, AnthropicProvider),
        ("openai", {"openai_api_key": "ok"}, OpenAIProvider),
        ("gemini", {"gemini_api_key": "gk"}, GeminiProvider),
    ]
    for name, keys, cls in cases:
        settings = make_settings(llm_provider=name, llm_model="test-model", **keys)

        provider = build_llm_provider(http_client, settings)

        assert isinstance(provider, cls)
        assert provider.name == name
        assert provider.model == "test-model"


async def test_missing_key_for_selected_provider_raises(http_client):
    settings = make_settings(llm_provider="openai")  # no openai key

    with pytest.raises(LLMAuthError):
        build_llm_provider(http_client, settings)


async def test_unknown_provider_raises(http_client):
    settings = make_settings(llm_provider="llama-at-home")

    with pytest.raises(LLMError):
        build_llm_provider(http_client, settings)


async def test_provider_name_is_case_insensitive(http_client):
    settings = make_settings(llm_provider="  Anthropic ", anthropic_api_key="ak")

    provider = build_llm_provider(http_client, settings)

    assert isinstance(provider, AnthropicProvider)
