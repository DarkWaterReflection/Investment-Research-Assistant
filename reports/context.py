"""Build the report view-model from a completed job's artifacts.

The context builder resolves every finding's evidence IDs into numbered
footnotes ([1], [2], …) assigned in reading order — synthesis first, then
sections — and produces the numbered source register. IDs that don't resolve
to corpus evidence are dropped defensively (the validation layer should have
already stripped them). Templates receive only this context: no template ever
touches raw pipeline objects.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from analysis.schemas import AnalysisResult
from collectors.base import Evidence
from core.types import Basis, Confidence
from llm.schemas import Finding
from processors.pipeline import ProcessedCorpus


class CitedFinding(BaseModel):
    """A finding with its evidence IDs resolved to footnote numbers."""

    claim: str
    basis: Basis
    confidence: Confidence
    citations: list[int] = Field(default_factory=list)


class ReportSection(BaseModel):
    title: str
    summary: str
    findings: list[CitedFinding] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SourceRef(BaseModel):
    """One numbered entry in the source register."""

    number: int
    evidence_id: str
    title: str
    url: str
    collector: str
    published: str | None = None


class TimelineRow(BaseModel):
    date: str
    title: str
    category: str


class ReportStats(BaseModel):
    stage: str
    evidence_count: int
    quarantined_count: int
    merged_count: int
    conflict_count: int
    total_cost_usd: float


class ReportContext(BaseModel):
    """Everything a report template may render."""

    company: str
    generated_at: datetime
    stats: ReportStats
    executive_summary: str | None = None
    investment_thesis: str | None = None
    strengths: list[CitedFinding] = Field(default_factory=list)
    concerns: list[CitedFinding] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    sections: list[ReportSection] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    timeline: list[TimelineRow] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class _Numberer:
    """Assigns stable footnote numbers to evidence on first citation."""

    def __init__(self, evidence: list[Evidence]) -> None:
        self._by_id = {item.id: item for item in evidence}
        self._numbers: dict[str, int] = {}
        self._sources: list[SourceRef] = []

    def cite(self, evidence_ids: list[str]) -> list[int]:
        numbers: list[int] = []
        for evidence_id in evidence_ids:
            item = self._by_id.get(evidence_id)
            if item is None:
                continue  # validator should have stripped it; never render a dead ref
            if evidence_id not in self._numbers:
                self._numbers[evidence_id] = len(self._sources) + 1
                self._sources.append(
                    SourceRef(
                        number=self._numbers[evidence_id],
                        evidence_id=evidence_id,
                        title=item.title,
                        url=item.source_url,
                        collector=item.collector,
                        published=(
                            item.published_at.date().isoformat() if item.published_at else None
                        ),
                    )
                )
            numbers.append(self._numbers[evidence_id])
        return numbers

    @property
    def sources(self) -> list[SourceRef]:
        return self._sources


def build_report_context(
    *,
    company: str,
    corpus: ProcessedCorpus,
    analysis: AnalysisResult,
    stage: str,
    total_cost_usd: float,
    warnings: list[str] | None = None,
    generated_at: datetime | None = None,
) -> ReportContext:
    numberer = _Numberer(corpus.evidence)

    def cited(finding: Finding) -> CitedFinding:
        return CitedFinding(
            claim=finding.claim,
            basis=finding.basis,
            confidence=finding.confidence,
            citations=numberer.cite(finding.evidence_ids),
        )

    synthesis = analysis.synthesis
    strengths = [cited(f) for f in synthesis.strengths] if synthesis else []
    concerns = [cited(f) for f in synthesis.concerns] if synthesis else []
    sections = [
        ReportSection(
            title=section.title,
            summary=section.analysis.summary,
            findings=[cited(f) for f in section.analysis.findings],
            warnings=section.warnings,
        )
        for section in analysis.sections
    ]

    return ReportContext(
        company=company,
        generated_at=generated_at or datetime.now(UTC),
        stats=ReportStats(
            stage=stage,
            evidence_count=len(corpus.evidence),
            quarantined_count=len(corpus.quarantined),
            merged_count=len(corpus.merged),
            conflict_count=len(corpus.conflicts),
            total_cost_usd=total_cost_usd,
        ),
        executive_summary=synthesis.executive_summary if synthesis else None,
        investment_thesis=synthesis.investment_thesis if synthesis else None,
        strengths=strengths,
        concerns=concerns,
        open_questions=list(synthesis.open_questions) if synthesis else [],
        sections=sections,
        conflicts=[conflict.description for conflict in corpus.conflicts],
        timeline=[
            TimelineRow(
                date=event.occurred_at.date().isoformat(),
                title=event.title,
                category=str(event.category),
            )
            for event in corpus.timeline
        ],
        sources=numberer.sources,
        warnings=list(warnings or []),
    )
