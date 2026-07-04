"""Structured outputs of the analysis stage.

Every analysis pass emits a SectionAnalysis (summary + cited findings); the
final synthesis pass reads the sections — not raw evidence — and emits the
memo-level view. AnalysisResult carries full usage accounting so cost is
observable per job, per pass, per call.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from llm.base import LLMUsage
from llm.schemas import Finding


class SectionAnalysis(BaseModel):
    """What the model returns for one analysis pass."""

    summary: str = Field(min_length=1)
    findings: list[Finding] = Field(default_factory=list)


class MemoSynthesis(BaseModel):
    """The memo-level synthesis built from completed sections."""

    executive_summary: str = Field(min_length=1)
    investment_thesis: str = Field(min_length=1)
    strengths: list[Finding] = Field(default_factory=list)
    concerns: list[Finding] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class SectionResult(BaseModel):
    """One completed pass: its output plus provenance and diagnostics."""

    name: str
    title: str
    analysis: SectionAnalysis
    evidence_used: list[str] = Field(default_factory=list)  # ids shown to the model
    warnings: list[str] = Field(default_factory=list)  # citation strips/downgrades


class AnalysisResult(BaseModel):
    """Everything the analysis stage produced for one research job."""

    sections: list[SectionResult] = Field(default_factory=list)
    synthesis: MemoSynthesis | None = None
    usage: list[LLMUsage] = Field(default_factory=list)
    total_cost_usd: float = 0.0
    skipped_passes: list[str] = Field(default_factory=list)
    budget_exhausted: bool = False
    warnings: list[str] = Field(default_factory=list)
