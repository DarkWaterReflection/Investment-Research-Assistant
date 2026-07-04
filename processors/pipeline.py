"""The validation pipeline: raw Evidence in, a vetted ProcessedCorpus out.

Stages run in a fixed order — clean, dedupe, entity-resolve, score, detect
conflicts, build timeline — each one auditable in isolation. The pipeline
surfaces warnings (heavy quarantine, unresolved conflicts) rather than making
silent judgment calls.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from collectors.base import CompanyTarget, Evidence
from processors.cleaning import clean_evidence
from processors.conflicts import Conflict, detect_conflicts
from processors.dedupe import dedupe_evidence
from processors.entity_resolution import resolve_entities
from processors.reliability import apply_confidence
from processors.timeline import TimelineEvent, build_timeline

_QUARANTINE_WARN_RATIO = 0.30


class ProcessedCorpus(BaseModel):
    """The output of the validation pipeline — vetted, scored, and dated."""

    evidence: list[Evidence] = Field(default_factory=list)
    quarantined: list[Evidence] = Field(default_factory=list)
    merged: list[tuple[str, str]] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ValidationPipeline:
    """Runs Evidence through the full clean-to-timeline validation sequence."""

    def run(self, evidence: list[Evidence], target: CompanyTarget) -> ProcessedCorpus:
        """Process raw ``evidence`` about ``target`` into a ProcessedCorpus."""
        cleaned = [clean_evidence(item) for item in evidence]

        deduped = dedupe_evidence(cleaned)
        resolution = resolve_entities(deduped.kept, target)
        scored = apply_confidence(resolution.matched)
        conflicts = detect_conflicts(scored)
        timeline = build_timeline(scored)

        warnings = self._warnings(
            matched=len(resolution.matched),
            quarantined=len(resolution.quarantined),
            conflicts=len(conflicts),
        )

        return ProcessedCorpus(
            evidence=scored,
            quarantined=resolution.quarantined,
            merged=deduped.merged,
            conflicts=conflicts,
            timeline=timeline,
            warnings=warnings,
        )

    @staticmethod
    def _warnings(*, matched: int, quarantined: int, conflicts: int) -> list[str]:
        warnings: list[str] = []
        total = matched + quarantined
        if total > 0 and quarantined / total > _QUARANTINE_WARN_RATIO:
            pct = round(100 * quarantined / total)
            warnings.append(
                f"{pct}% of evidence was quarantined as off-target "
                f"({quarantined}/{total}); target resolution may be too narrow."
            )
        if conflicts:
            warnings.append(
                f"{conflicts} unresolved conflict(s) detected; review before analysis."
            )
        return warnings
