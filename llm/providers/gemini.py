"""Google Gemini generateContent adapter.

Gemini's typed responseSchema dialect rejects several JSON-schema keywords
Pydantic emits ($defs, allOf), so instead we request JSON mime type and embed
the schema in the system instruction. llm.validation enforces it either way,
including the one repair retry for outputs that drift.
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

GENERATE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiProvider(BaseLLMProvider):
    name = "gemini"

    def __init__(self, client: httpx.AsyncClient, api_key: str, model: str) -> None:
        self._client = client
        self.model = model
        self._headers = {"x-goog-api-key": api_key}

    async def complete_structured(
        self,
        *,
        system: str,
        prompt: str,
        schema: type[BaseModel],
        max_tokens: int = 4096,
    ) -> LLMResult:
        schema_text = json.dumps(schema.model_json_schema())
        body = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            f"{system}\n\nRespond with a single JSON object conforming "
                            f"exactly to this JSON schema:\n{schema_text}"
                        )
                    }
                ]
            },
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "maxOutputTokens": max_tokens,
            },
        }
        url = GENERATE_URL.format(model=self.model)
        start = time.perf_counter()
        response = await with_retries(
            lambda: self._client.post(url, json=body, headers=self._headers)
        )
        latency = time.perf_counter() - start
        raise_for_llm_status(self.name, response)
        data = response.json()

        payload = self._extract_json(data)
        tokens = data.get("usageMetadata", {})
        input_tokens = int(tokens.get("promptTokenCount", 0))
        output_tokens = int(tokens.get("candidatesTokenCount", 0))
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

    def _extract_json(self, data: dict[str, Any]) -> dict[str, Any]:
        candidates = data.get("candidates", [])
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text = next((p["text"] for p in parts if "text" in p), None)
        if text is None:
            raise MalformedOutputError(self.name, "response contained no text part")
        stripped = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise MalformedOutputError(self.name, f"response text not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise MalformedOutputError(self.name, "response was not a JSON object")
        return payload
