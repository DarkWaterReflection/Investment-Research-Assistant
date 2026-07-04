"""Anthropic Messages API adapter.

Structured output is obtained by forcing a single tool call ("emit") whose
input schema is the requested Pydantic model's JSON schema, so the payload
arrives as parsed JSON rather than free text.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
from pydantic import BaseModel

from collectors.resilience import with_retries
from llm.base import (
    BaseLLMProvider,
    LLMResult,
    LLMUsage,
    MalformedOutputError,
    raise_for_llm_status,
)
from llm.pricing import estimate_cost_usd

MESSAGES_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
TOOL_NAME = "emit"


class AnthropicProvider(BaseLLMProvider):
    name = "anthropic"

    def __init__(self, client: httpx.AsyncClient, api_key: str, model: str) -> None:
        self._client = client
        self.model = model
        self._headers = {
            "x-api-key": api_key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        }

    async def complete_structured(
        self,
        *,
        system: str,
        prompt: str,
        schema: type[BaseModel],
        max_tokens: int = 4096,
    ) -> LLMResult:
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
            "tools": [
                {
                    "name": TOOL_NAME,
                    "description": "Emit the structured analysis result.",
                    "input_schema": schema.model_json_schema(),
                }
            ],
            "tool_choice": {"type": "tool", "name": TOOL_NAME},
        }
        start = time.perf_counter()
        response = await with_retries(
            lambda: self._client.post(MESSAGES_URL, json=body, headers=self._headers)
        )
        latency = time.perf_counter() - start
        raise_for_llm_status(self.name, response)
        data = response.json()

        payload = self._extract_tool_input(data)
        tokens = data.get("usage", {})
        input_tokens = int(tokens.get("input_tokens", 0))
        output_tokens = int(tokens.get("output_tokens", 0))
        return LLMResult(
            payload=payload,
            usage=LLMUsage(
                provider=self.name,
                model=self.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=estimate_cost_usd(self.model, input_tokens, output_tokens),
                latency_seconds=latency,
            ),
        )

    def _extract_tool_input(self, data: dict[str, Any]) -> dict[str, Any]:
        for block in data.get("content", []):
            if block.get("type") == "tool_use" and isinstance(block.get("input"), dict):
                return dict(block["input"])
        raise MalformedOutputError(self.name, "response contained no tool_use block")
