"""Confidence scoring for Evidence.

A datum's trustworthiness is a product of three factors: how reliable its
source is, how fresh it is, and how well the rest of the corpus corroborates
it. Each factor is transparent and bounded so a reader can reconstruct why any
score came out the way it did.
"""

from __future__ import annotations

from datetime import UTC, datetime

from collectors.base import Evidence
from processors._text import content_similarity

_HALF_LIFE_DAYS = 365.0
_CORROBORATION_SIMILARITY = 0.3
_CORROBORATION_PER_ITEM = 0.1
_CORROBORATION_CAP = 1.3


def _as_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment


def _recency_decay(evidence: Evidence, now: datetime) -> float:
    if evidence.published_at is None:
        return 1.0
    age_days = (now - _as_utc(evidence.published_at)).total_seconds() / 86400.0
    if age_days <= 0:
        return 1.0
    return float(0.5 ** (age_days / _HALF_LIFE_DAYS))


def _corroboration_boost(evidence: Evidence, corpus: list[Evidence]) -> float:
    supporters = 0
    for other in corpus:
        if other.id == evidence.id or other.category != evidence.category:
            continue
        if content_similarity(evidence.content, other.content) >= _CORROBORATION_SIMILARITY:
            supporters += 1
    return min(1.0 + _CORROBORATION_PER_ITEM * supporters, _CORROBORATION_CAP)


def score_confidence(evidence: Evidence, corpus: list[Evidence]) -> float:
    """Confidence in [0, 1] = source prior x recency decay x corroboration.

    Recency uses a 365-day half-life on ``published_at`` (no decay when it is
    absent). Corroboration boosts by 0.1 per other same-category item with
    content similarity >= 0.3, capped at 1.3x.
    """
    now = datetime.now(UTC)
    raw = (
        evidence.reliability
        * _recency_decay(evidence, now)
        * _corroboration_boost(evidence, corpus)
    )
    return max(0.0, min(1.0, raw))


def apply_confidence(evidence: list[Evidence]) -> list[Evidence]:
    """Return copies of ``evidence`` with ``confidence`` scored against the set."""
    return [
        item.model_copy(update={"confidence": score_confidence(item, evidence)})
        for item in evidence
    ]
