"""Provider adapter tests against mocked vendor APIs (respx — no live calls).

Each provider is checked for: request shape (auth, forced structured output),
payload extraction, usage + cost accounting, and typed error mapping.
"""

import json

import pytest
import respx
from pydantic import BaseModel

from llm.base import (
    LLMAuthError,
    LLMRateLimitedError,
    LLMUnavailableError,
    MalformedOutputError,
)
from llm.providers.anthropic import MESSAGES_URL, AnthropicProvider
from llm.providers.gemini import GENERATE_URL, GeminiProvider
from llm.providers.openai import CHAT_URL, OpenAIProvider
from llm.schemas import Finding


class Section(BaseModel):
    summary: str
    findings: list[Finding]


PAYLOAD = {
    "summary": "Acme is growing.",
    "findings": [
        {
            "claim": "Raised $40M Series B",
            "basis": "sourced",
            "evidence_ids": ["ev1"],
            "confidence": "high",
        }
    ],
}

ANTHROPIC_FIXTURE = {
    "content": [
        {"type": "text", "text": "Calling the tool."},
        {"type": "tool_use", "name": "emit", "input": PAYLOAD},
    ],
    "usage": {"input_tokens": 1000, "output_tokens": 200},
}

OPENAI_FIXTURE = {
    "choices": [
        {
            "message": {
                "tool_calls": [
                    {"function": {"name": "emit", "arguments": json.dumps(PAYLOAD)}}
                ]
            }
        }
    ],
    "usage": {"prompt_tokens": 800, "completion_tokens": 150},
}

GEMINI_FIXTURE = {
    "candidates": [
        {"content": {"parts": [{"text": f"```json\n{json.dumps(PAYLOAD)}\n```"}]}}
    ],
    "usageMetadata": {"promptTokenCount": 600, "candidatesTokenCount": 120},
}


async def complete(provider):
    return await provider.complete_structured(
        system="You are an analyst.", prompt="Analyze Acme.", schema=Section
    )


# --- Anthropic ---


@respx.mock
async def test_anthropic_request_shape_payload_and_cost(http_client):
    route = respx.post(MESSAGES_URL).respond(json=ANTHROPIC_FIXTURE)
    provider = AnthropicProvider(http_client, "ak-test", "claude-sonnet-5")

    result = await complete(provider)

    request = route.calls.last.request
    body = json.loads(request.content)
    assert request.headers["x-api-key"] == "ak-test"
    assert body["tool_choice"] == {"type": "tool", "name": "emit"}
    assert body["tools"][0]["input_schema"]["title"] == "Section"
    assert result.payload == PAYLOAD
    assert result.usage.input_tokens == 1000
    assert result.usage.output_tokens == 200
    # claude-sonnet-5: 1000 * $3/M + 200 * $15/M
    assert result.usage.cost_usd == pytest.approx(0.006)
    assert result.usage.latency_seconds >= 0.0


@respx.mock
async def test_anthropic_auth_error_is_typed(http_client):
    respx.post(MESSAGES_URL).respond(status_code=401, json={"error": "bad key"})
    provider = AnthropicProvider(http_client, "bad-key", "claude-sonnet-5")

    with pytest.raises(LLMAuthError):
        await complete(provider)


@respx.mock
async def test_anthropic_missing_tool_use_is_malformed(http_client):
    respx.post(MESSAGES_URL).respond(
        json={"content": [{"type": "text", "text": "no tool"}], "usage": {}}
    )
    provider = AnthropicProvider(http_client, "ak-test", "claude-sonnet-5")

    with pytest.raises(MalformedOutputError):
        await complete(provider)


# --- OpenAI ---


@respx.mock
async def test_openai_request_shape_payload_and_cost(http_client):
    route = respx.post(CHAT_URL).respond(json=OPENAI_FIXTURE)
    provider = OpenAIProvider(http_client, "sk-test", "gpt-4o")

    result = await complete(provider)

    request = route.calls.last.request
    body = json.loads(request.content)
    assert request.headers["Authorization"] == "Bearer sk-test"
    assert body["tool_choice"] == {"type": "function", "function": {"name": "emit"}}
    assert body["messages"][0]["role"] == "system"
    assert result.payload == PAYLOAD
    # gpt-4o: 800 * $2.5/M + 150 * $10/M
    assert result.usage.cost_usd == pytest.approx(0.0035)


@respx.mock
async def test_openai_persistent_rate_limit_is_typed(http_client):
    respx.post(CHAT_URL).respond(status_code=429)
    provider = OpenAIProvider(http_client, "sk-test", "gpt-4o")

    with pytest.raises(LLMRateLimitedError):
        await complete(provider)


@respx.mock
async def test_openai_unparseable_arguments_is_malformed(http_client):
    fixture = {
        "choices": [
            {"message": {"tool_calls": [{"function": {"arguments": "not json {"}}]}}
        ],
        "usage": {},
    }
    respx.post(CHAT_URL).respond(json=fixture)
    provider = OpenAIProvider(http_client, "sk-test", "gpt-4o")

    with pytest.raises(MalformedOutputError):
        await complete(provider)


# --- Gemini ---


@respx.mock
async def test_gemini_request_shape_payload_and_cost(http_client):
    url = GENERATE_URL.format(model="gemini-2.5-pro")
    route = respx.post(url).respond(json=GEMINI_FIXTURE)
    provider = GeminiProvider(http_client, "gk-test", "gemini-2.5-pro")

    result = await complete(provider)

    request = route.calls.last.request
    body = json.loads(request.content)
    assert request.headers["x-goog-api-key"] == "gk-test"
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert "JSON schema" in body["systemInstruction"]["parts"][0]["text"]
    assert result.payload == PAYLOAD  # markdown fences stripped
    # gemini-2.5-pro: 600 * $1.25/M + 120 * $10/M
    assert result.usage.cost_usd == pytest.approx(0.00195)


@respx.mock
async def test_gemini_server_error_is_typed(http_client):
    url = GENERATE_URL.format(model="gemini-2.5-pro")
    respx.post(url).respond(status_code=503)
    provider = GeminiProvider(http_client, "gk-test", "gemini-2.5-pro")

    with pytest.raises(LLMUnavailableError):
        await complete(provider)


@respx.mock
async def test_gemini_non_json_text_is_malformed(http_client):
    url = GENERATE_URL.format(model="gemini-2.5-pro")
    fixture = {"candidates": [{"content": {"parts": [{"text": "I cannot comply."}]}}]}
    respx.post(url).respond(json=fixture)
    provider = GeminiProvider(http_client, "gk-test", "gemini-2.5-pro")

    with pytest.raises(MalformedOutputError):
        await complete(provider)
