"""OpenAI Chat Completions adapter.

Structured output via forced function calling: one function ("emit") whose
parameters are the requested Pydantic model's JSON schema. The arguments
string is parsed here; schema validation happens in llm.validation.
"""

from __future__ import annotations

import json
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

CHAT_URL = "https://api.openai.com/v1/chat/completions"
TOOL_NAME = "emit"


class OpenAIProvider(BaseLLMProvider):
    name = "openai"

    def __init__(self, client: httpx.AsyncClient, api_key: str, model: str) -> None:
        self._client = client
        self.model = model
        self._headers = {"Authorization": f"Bearer {api_key}"}

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
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": TOOL_NAME,
                        "description": "Emit the structured analysis result.",
                        "parameters": schema.model_json_schema(),
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": TOOL_NAME}},
        }
        start = time.perf_counter()
        response = await with_retries(
            lambda: self._client.post(CHAT_URL, json=body, headers=self._headers)
        )
        latency = time.perf_counter() - start
        raise_for_llm_status(self.name, response)
        data = response.json()

        payload = self._extract_arguments(data)
        tokens = data.get("usage", {})
        input_tokens = int(tokens.get("prompt_tokens", 0))
        output_tokens = int(tokens.get("completion_tokens", 0))
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

    def _extract_arguments(self, data: dict[str, Any]) -> dict[str, Any]:
        choices = data.get("choices", [])
        tool_calls = choices[0].get("message", {}).get("tool_calls", []) if choices else []
        if not tool_calls:
            raise MalformedOutputError(self.name, "response contained no tool call")
        arguments = tool_calls[0].get("function", {}).get("arguments", "")
        try:
            payload = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise MalformedOutputError(self.name, f"tool arguments not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise MalformedOutputError(self.name, "tool arguments were not a JSON object")
        return payload
