"""Structured-output building blocks shared by all analysis passes.

Finding is the unit of analytical output: every claim declares its provenance
class and, when sourced, must cite Evidence IDs from the processed corpus.
Citation enforcement lives in llm.validation, which needs the corpus to know
which IDs are real.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.types import Basis, Confidence


class Finding(BaseModel):
    """A single analytical claim with provenance and confidence."""

    claim: str = Field(min_length=1)
    basis: Basis
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: Confidence
