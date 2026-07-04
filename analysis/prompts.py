"""Prompt construction for analysis passes.

Evidence is rendered with its ID, provenance and confidence so the model can
cite precisely; content is capped per item and items per pass so a large
corpus cannot blow the context or the budget. Selection prefers the highest-
confidence evidence, falling back to the reliability prior when unscored.
"""

from __future__ import annotations

from analysis.passes import PassSpec
from analysis.schemas import SectionResult
from collectors.base import Evidence
from core.types import DataCategory
from processors.conflicts import Conflict

MAX_EVIDENCE_PER_PASS = 25
MAX_CONTENT_CHARS = 700

SYSTEM_PROMPT = (
    "You are a rigorous investment analyst performing company due diligence. "
    "You work only from the evidence provided — never from your own knowledge "
    "of the company. Every finding must declare its basis: 'sourced' findings "
    "must cite the exact evidence ids (the [id] tags) that support them; use "
    "'inferred' for conclusions you draw beyond what a source states, and "
    "'assumption' for premises you cannot support at all. Never invent "
    "evidence ids. Where sources disagree, present the disagreement instead "
    "of resolving it. Be specific, be skeptical, and say so when the evidence "
    "is thin."
)


def select_evidence(
    evidence: list[Evidence], categories: frozenset[DataCategory]
) -> list[Evidence]:
    """The highest-confidence evidence in the given categories, capped."""
    relevant = [item for item in evidence if item.category in categories]
    relevant.sort(
        key=lambda item: item.confidence if item.confidence is not None else item.reliability,
        reverse=True,
    )
    return relevant[:MAX_EVIDENCE_PER_PASS]


def format_evidence(items: list[Evidence]) -> str:
    blocks: list[str] = []
    for item in items:
        confidence = item.confidence if item.confidence is not None else item.reliability
        published = item.published_at.date().isoformat() if item.published_at else "unknown"
        content = item.content[:MAX_CONTENT_CHARS]
        blocks.append(
            f"[{item.id}] category={item.category} source={item.collector} "
            f"confidence={confidence:.2f} published={published}\n"
            f"Title: {item.title}\n"
            f"{content}"
        )
    return "\n\n".join(blocks)


def format_conflicts(conflicts: list[Conflict]) -> str:
    if not conflicts:
        return "None detected."
    lines = [
        f"- {conflict.description} (values: {', '.join(conflict.values)}; "
        f"evidence: {', '.join(conflict.evidence_ids)})"
        for conflict in conflicts
    ]
    return "\n".join(lines)


def build_pass_prompt(
    company: str,
    spec: PassSpec,
    items: list[Evidence],
    *,
    conflicts: list[Conflict] | None = None,
    quarantined_count: int = 0,
) -> str:
    parts = [
        f"Company under research: {company}",
        f"Task — {spec.title}: {spec.instructions}",
        f"Evidence ({len(items)} items):\n\n{format_evidence(items)}",
    ]
    if spec.include_conflicts:
        parts.append(f"Unresolved conflicts between sources:\n{format_conflicts(conflicts or [])}")
        parts.append(
            f"{quarantined_count} evidence item(s) were quarantined as possibly "
            "referring to a different entity with a similar name."
        )
    parts.append(
        "Return a summary of your assessment and a list of findings, each with "
        "its basis, confidence, and supporting evidence ids."
    )
    return "\n\n".join(parts)


def build_synthesis_prompt(company: str, sections: list[SectionResult]) -> str:
    rendered: list[str] = []
    for section in sections:
        findings = "\n".join(
            f"- [{finding.basis}, {finding.confidence}] {finding.claim} "
            f"(evidence: {', '.join(finding.evidence_ids) or 'none'})"
            for finding in section.analysis.findings
        )
        rendered.append(
            f"## {section.title}\n{section.analysis.summary}\n{findings or '(no findings)'}"
        )
    sections_text = "\n\n".join(rendered)
    return (
        f"Company under research: {company}\n\n"
        "Below are the completed section analyses of the investment memo. "
        "Synthesize them into: an executive summary, an investment thesis, the "
        "key strengths and concerns (as findings — reuse the evidence ids "
        "already cited in the sections; never invent new ones), and the open "
        "questions a diligence team should pursue next.\n\n"
        f"{sections_text}"
    )
