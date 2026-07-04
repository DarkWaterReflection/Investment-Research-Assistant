"""LLM provider contract — the analysis layer's only view of a language model.

Providers return structured payloads (raw dicts produced via each vendor's
tool-use / JSON mode) plus usage accounting. Parsing into Pydantic schemas and
citation enforcement live in llm.validation, so every provider stays a thin,
swappable transport adapter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx
from pydantic import BaseModel, Field


class LLMUsage(BaseModel):
    """Token, cost and latency accounting for a single model call."""

    provider: str
    model: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_usd: float | None = None  # None when the model is not in the pricing table
    latency_seconds: float = Field(ge=0.0)


class LLMResult(BaseModel):
    """One structured completion: the raw payload plus its usage record."""

    payload: dict[str, Any]
    usage: LLMUsage


class LLMError(Exception):
    """Base class for typed LLM failures."""

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        super().__init__(f"[{provider}] {message}")


class LLMAuthError(LLMError):
    """Missing or rejected credentials."""


class LLMRateLimitedError(LLMError):
    """Provider throttled us even after retries."""


class LLMUnavailableError(LLMError):
    """Provider down or returning server errors."""


class MalformedOutputError(LLMError):
    """The model's output could not be parsed as the requested structure."""


class BaseLLMProvider(ABC):
    """Adapter contract every LLM vendor implements.

    complete_structured must return the model's output as a dict matching the
    given JSON schema as closely as the vendor allows; it never validates.
    """

    name: str
    model: str

    @abstractmethod
    async def complete_structured(
        self,
        *,
        system: str,
        prompt: str,
        schema: type[BaseModel],
        max_tokens: int = 4096,
    ) -> LLMResult:
        """Run one completion constrained to the schema. Raises LLMError subtypes."""


def raise_for_llm_status(provider: str, response: httpx.Response) -> None:
    """Map non-success HTTP statuses to typed LLM errors."""
    status = response.status_code
    if status in (200, 201):
        return
    detail = response.text[:300]
    if status in (401, 403):
        raise LLMAuthError(provider, f"credentials rejected ({status}): {detail}")
    if status == 429:
        raise LLMRateLimitedError(provider, f"rate limited after retries: {detail}")
    if status >= 500:
        raise LLMUnavailableError(provider, f"server error {status}: {detail}")
    raise LLMError(provider, f"unexpected status {status}: {detail}")
