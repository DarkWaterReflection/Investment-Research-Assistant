"""Conflict detection across funding evidence.

When two sources disagree on the size of the same funding round, that
disagreement is a finding, not a bug. Conflicts are surfaced with both sides
and their supporting evidence intact — never auto-resolved, because picking a
winner is an analyst's call, not a preprocessor's.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from collectors.base import Evidence
from core.types import DataCategory
from processors.ner import extract_entities

_AMOUNT_TOLERANCE = 0.10  # amounts within 10% are treated as agreement

# Ordered so more specific labels (Pre-Seed) are considered before Seed.
_ROUND_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Pre-Seed", re.compile(r"pre[\s-]?seed", re.IGNORECASE)),
    ("Seed", re.compile(r"\bseed\b", re.IGNORECASE)),
    ("Series A", re.compile(r"\bseries[\s-]?a\b", re.IGNORECASE)),
    ("Series B", re.compile(r"\bseries[\s-]?b\b", re.IGNORECASE)),
    ("Series C", re.compile(r"\bseries[\s-]?c\b", re.IGNORECASE)),
    ("Series D", re.compile(r"\bseries[\s-]?d\b", re.IGNORECASE)),
    ("Series E", re.compile(r"\bseries[\s-]?e\b", re.IGNORECASE)),
    ("Series F", re.compile(r"\bseries[\s-]?f\b", re.IGNORECASE)),
]


class Conflict(BaseModel):
    """A surfaced disagreement between evidence items about one field."""

    field: str
    values: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    description: str


def _rounds_in(text: str) -> set[str]:
    rounds = {label for label, pattern in _ROUND_PATTERNS if pattern.search(text)}
    if "Pre-Seed" in rounds:
        rounds.discard("Seed")  # "pre-seed" also matches the bare "seed" pattern
    return rounds


def _format_amount(amount: float) -> str:
    return f"{amount:,.0f}"


def detect_conflicts(evidence: list[Evidence]) -> list[Conflict]:
    """Find funding rounds whose reported amounts disagree by more than 10%.

    Only FUNDING-category evidence is considered. Each item's representative
    figure is the largest money amount it mentions (the headline round size);
    items are grouped by the funding round they name, and a conflict is raised
    when the smallest and largest figures in a group differ by >10%.
    """
    by_round: dict[str, list[tuple[float, str]]] = {}
    for item in evidence:
        if item.category != DataCategory.FUNDING:
            continue
        text = f"{item.title}\n{item.content}"
        rounds = _rounds_in(text)
        if not rounds:
            continue
        money = extract_entities(text).money
        if not money:
            continue
        headline = max(mention.amount for mention in money)
        for label in rounds:
            by_round.setdefault(label, []).append((headline, item.id))

    conflicts: list[Conflict] = []
    for label in (name for name, _ in _ROUND_PATTERNS):
        entries = by_round.get(label)
        if entries is None or len(entries) < 2:
            continue
        amounts = [amount for amount, _ in entries]
        low, high = min(amounts), max(amounts)
        if low <= 0 or high <= low * (1 + _AMOUNT_TOLERANCE):
            continue
        ids: list[str] = []
        for _, evidence_id in entries:
            if evidence_id not in ids:
                ids.append(evidence_id)
        values = [_format_amount(a) for a in sorted(set(amounts))]
        conflicts.append(
            Conflict(
                field=f"funding_amount:{label}",
                values=values,
                evidence_ids=ids,
                description=(
                    f"Conflicting {label} funding amounts reported "
                    f"across {len(ids)} sources: {', '.join(values)}."
                ),
            )
        )
    return conflicts
