from datetime import UTC, datetime, timedelta

import pytest
from corpus import build_corpus

from collectors.base import Evidence
from core.types import DataCategory
from processors.reliability import apply_confidence, score_confidence


def make_evidence(**overrides):
    defaults = dict(
        company="Acme Robotics",
        category=DataCategory.NEWS,
        title="A headline",
        content="Acme Robotics closed a Series B round to expand manufacturing.",
        source_url="https://news.example/story",
        collector="serpapi",
        reliability=0.8,
    )
    return Evidence(**{**defaults, **overrides})


def _days_ago(days: float) -> datetime:
    return datetime.now(UTC) - timedelta(days=days)


def test_fresh_uncorroborated_confidence_equals_reliability():
    ev = make_evidence(reliability=0.8, published_at=None)
    # Alone in its corpus, no recency decay -> confidence == reliability.
    assert score_confidence(ev, [ev]) == 0.8


def test_confidence_always_within_unit_interval():
    for ev in apply_confidence(build_corpus()):
        assert 0.0 <= ev.confidence <= 1.0


def test_recency_decay_lowers_older_evidence():
    fresh = make_evidence(reliability=0.9, published_at=_days_ago(1))
    old = make_evidence(reliability=0.9, published_at=_days_ago(365))
    assert score_confidence(old, [old]) < score_confidence(fresh, [fresh])


def test_one_year_old_is_about_half():
    ev = make_evidence(reliability=0.8, published_at=_days_ago(365))
    # 365-day half-life: ~0.8 * 0.5 with no corroboration.
    assert score_confidence(ev, [ev]) == pytest.approx(0.4, abs=0.02)


def test_corroboration_raises_confidence():
    subject = make_evidence(reliability=0.6, published_at=None)
    supporter = make_evidence(
        reliability=0.6,
        published_at=None,
        content="Acme Robotics closed a Series B round to expand manufacturing operations.",
    )
    alone = score_confidence(subject, [subject])
    supported = score_confidence(subject, [subject, supporter])
    assert supported > alone


def test_corroboration_ignores_different_category():
    subject = make_evidence(category=DataCategory.NEWS, published_at=None)
    other_category = make_evidence(
        category=DataCategory.FUNDING,
        published_at=None,
        content=subject.content,
    )
    assert score_confidence(subject, [subject, other_category]) == score_confidence(
        subject, [subject]
    )


def test_apply_confidence_does_not_mutate_inputs():
    corpus = build_corpus()
    apply_confidence(corpus)
    assert all(item.confidence is None for item in corpus)


def test_apply_confidence_sets_confidence_on_copies():
    scored = apply_confidence(build_corpus())
    assert all(item.confidence is not None for item in scored)
