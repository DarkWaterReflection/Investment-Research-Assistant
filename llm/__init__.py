"""LLM abstraction layer: provider adapters, structured output, citation enforcement."""

from llm.base import (
    BaseLLMProvider,
    LLMAuthError,
    LLMError,
    LLMRateLimitedError,
    LLMResult,
    LLMUnavailableError,
    LLMUsage,
    MalformedOutputError,
)
from llm.factory import build_llm_provider
from llm.schemas import Finding
from llm.validation import ValidatedOutput, generate_validated, iter_findings

__all__ = [
    "BaseLLMProvider",
    "Finding",
    "LLMAuthError",
    "LLMError",
    "LLMRateLimitedError",
    "LLMResult",
    "LLMUnavailableError",
    "LLMUsage",
    "MalformedOutputError",
    "ValidatedOutput",
    "build_llm_provider",
    "generate_validated",
    "iter_findings",
]
