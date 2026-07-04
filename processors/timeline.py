"""Chronological timeline assembly from Evidence.

A timeline orders evidence by when the underlying event happened
(``published_at``), falling back to when we collected it. Ordering is stable so
items sharing a timestamp keep their input order — reproducibility matters for
downstream reports.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel

from collectors.base import Evidence
from core.types import DataCategory


class TimelineEvent(BaseModel):
    """One dated point on the research timeline, linked to its evidence."""

    occurred_at: datetime
    title: str
    evidence_id: str
    category: DataCategory


def _occurred_at(evidence: Evidence) -> datetime:
    return evidence.published_at if evidence.published_at is not None else evidence.collected_at


def _sort_key(moment: datetime) -> datetime:
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment


def build_timeline(evidence: list[Evidence]) -> list[TimelineEvent]:
    """Build a timeline sorted ascending by event time (published, else collected).

    Sorting is stable: items with equal timestamps preserve their input order.
    """
    events = [
        TimelineEvent(
            occurred_at=_occurred_at(item),
            title=item.title,
            evidence_id=item.id,
            category=item.category,
        )
        for item in evidence
    ]
    return sorted(events, key=lambda event: _sort_key(event.occurred_at))
