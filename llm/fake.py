"""In-memory LLM provider for tests.

Scripted like a tape: each complete_structured call pops the next item —
a payload dict to return or an exception to raise — and records the call so
tests can assert on prompts, schemas and repair behaviour without any network
or API keys.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from llm.base import BaseLLMProvider, LLMResult, LLMUsage


@dataclass
class FakeCall:
    """What one complete_structured invocation asked for."""

    system: str
    prompt: str
    schema: type[BaseModel]
    max_tokens: int


class FakeLLM(BaseLLMProvider):
    name = "fake"
    model = "fake-1"

    def __init__(
        self, responses: list[dict[str, Any] | Exception], *, cost_per_call: float = 0.0
    ) -> None:
        self._queue = list(responses)
        self._cost_per_call = cost_per_call
        self.calls: list[FakeCall] = []

    async def complete_structured(
        self,
        *,
        system: str,
        prompt: str,
        schema: type[BaseModel],
        max_tokens: int = 4096,
    ) -> LLMResult:
        self.calls.append(
            FakeCall(system=system, prompt=prompt, schema=schema, max_tokens=max_tokens)
        )
        if not self._queue:
            raise AssertionError("FakeLLM ran out of scripted responses")
        item = self._queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return LLMResult(
            payload=item,
            usage=LLMUsage(
                provider=self.name,
                model=self.model,
                input_tokens=100,
                output_tokens=50,
                cost_usd=self._cost_per_call,
                latency_seconds=0.0,
            ),
        )
