"""Schema validation and citation enforcement for structured LLM output.

Two guarantees for every analysis pass:
1. The output parses into the requested Pydantic schema — one repair retry
   (the model sees its own output and the validation errors), then a typed
   MalformedOutputError.
2. Every SOURCED finding cites at least one Evidence ID that exists in the
   processed corpus — one repair retry, then the claim is downgraded to
   INFERRED rather than silently kept as fact. Unknown IDs are always
   stripped. Downgrades and strips are recorded as warnings, never hidden.

Only output-quality failures trigger the degrade path; infrastructure errors
(auth, rate limit, provider down) always propagate.
"""

from __future__ import annotations

import json
from collections.abc import Collection, Iterator
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, ValidationError

from core.types import Basis
from llm.base import BaseLLMProvider, LLMUsage, MalformedOutputError
from llm.schemas import Finding

T = TypeVar("T", bound=BaseModel)

_MAX_ECHO_CHARS = 4000  # cap on previous-output echoes inside repair prompts


class ValidatedOutput(BaseModel, Generic[T]):
    """A schema-valid, citation-checked result plus everything it cost."""

    output: T
    usage: list[LLMUsage]
    schema_repaired: bool = False
    citations_repaired: bool = False
    warnings: list[str] = Field(default_factory=list)


def iter_findings(value: Any) -> Iterator[Finding]:
    """Yield every Finding nested anywhere inside a validated output."""
    if isinstance(value, Finding):
        yield value
    elif isinstance(value, BaseModel):
        for name in type(value).model_fields:
            yield from iter_findings(getattr(value, name))
    elif isinstance(value, list | tuple | set):
        for item in value:
            yield from iter_findings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_findings(item)


async def generate_validated(
    provider: BaseLLMProvider,
    *,
    system: str,
    prompt: str,
    schema: type[T],
    known_evidence_ids: Collection[str],
    max_tokens: int = 4096,
) -> ValidatedOutput[T]:
    """Run one structured completion with validation, repair and enforcement."""
    usage: list[LLMUsage] = []
    known = set(known_evidence_ids)

    result = await provider.complete_structured(
        system=system, prompt=prompt, schema=schema, max_tokens=max_tokens
    )
    usage.append(result.usage)
    schema_repaired = False
    try:
        output = schema.model_validate(result.payload)
    except ValidationError as first_error:
        repair = await provider.complete_structured(
            system=system,
            prompt=_schema_repair_prompt(prompt, result.payload, first_error),
            schema=schema,
            max_tokens=max_tokens,
        )
        usage.append(repair.usage)
        try:
            output = schema.model_validate(repair.payload)
        except ValidationError as second_error:
            raise MalformedOutputError(
                provider.name,
                f"output failed schema validation after one repair: {second_error}",
            ) from second_error
        schema_repaired = True

    citations_repaired = False
    unsupported = _unsupported_claims(output, known)
    if unsupported:
        try:
            repair = await provider.complete_structured(
                system=system,
                prompt=_citation_repair_prompt(prompt, output, unsupported),
                schema=schema,
                max_tokens=max_tokens,
            )
            usage.append(repair.usage)
            candidate = schema.model_validate(repair.payload)
        except (ValidationError, MalformedOutputError):
            candidate = None  # keep the valid original; downgrade below
        if candidate is not None and not _unsupported_claims(candidate, known):
            output = candidate
            citations_repaired = True

    warnings = _sanitize_citations(output, known)
    return ValidatedOutput(
        output=output,
        usage=usage,
        schema_repaired=schema_repaired,
        citations_repaired=citations_repaired,
        warnings=warnings,
    )


def _unsupported_claims(output: BaseModel, known: set[str]) -> list[str]:
    """Claims marked SOURCED that cite no evidence ID present in the corpus."""
    return [
        finding.claim
        for finding in iter_findings(output)
        if finding.basis is Basis.SOURCED
        and not any(eid in known for eid in finding.evidence_ids)
    ]


def _sanitize_citations(output: BaseModel, known: set[str]) -> list[str]:
    """Strip unknown evidence IDs; downgrade uncited sourced claims to inferred."""
    warnings: list[str] = []
    for finding in iter_findings(output):
        if finding.basis is not Basis.SOURCED:
            continue
        valid = [eid for eid in finding.evidence_ids if eid in known]
        unknown = [eid for eid in finding.evidence_ids if eid not in known]
        if unknown:
            finding.evidence_ids = valid
            warnings.append(
                f"Dropped unknown evidence ids {unknown} from claim {finding.claim!r}."
            )
        if not valid:
            finding.basis = Basis.INFERRED
            warnings.append(
                f"Downgraded to inferred (no valid citations): {finding.claim!r}."
            )
    return warnings


def _schema_repair_prompt(prompt: str, payload: dict[str, Any], error: ValidationError) -> str:
    return (
        f"{prompt}\n\n"
        "Your previous response failed schema validation.\n"
        f"Previous response JSON:\n{json.dumps(payload)[:_MAX_ECHO_CHARS]}\n\n"
        f"Validation errors:\n{str(error)[:_MAX_ECHO_CHARS]}\n\n"
        "Return a corrected JSON object that satisfies the schema exactly."
    )


def _citation_repair_prompt(prompt: str, output: BaseModel, unsupported: list[str]) -> str:
    claims = "\n".join(f"- {claim}" for claim in unsupported)
    return (
        f"{prompt}\n\n"
        "Your previous response marked the following claims as 'sourced' without "
        "citing any evidence id that appears in the provided evidence:\n"
        f"{claims}\n\n"
        f"Previous response JSON:\n{output.model_dump_json()[:_MAX_ECHO_CHARS]}\n\n"
        "Fix it: every claim with basis 'sourced' must cite the exact evidence ids "
        "supporting it. If a claim has no supporting evidence, keep the claim but "
        "set its basis to 'inferred' with an empty evidence_ids list. Never invent ids."
    )
