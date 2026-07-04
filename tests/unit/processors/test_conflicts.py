from corpus import build_corpus

from collectors.base import Evidence
from core.types import DataCategory
from processors.conflicts import Conflict, detect_conflicts


def funding(**overrides):
    defaults = dict(
        company="Acme Robotics",
        category=DataCategory.FUNDING,
        title="Funding news",
        content="Acme raised money.",
        source_url="https://news.example/funding",
        collector="serpapi",
        reliability=0.6,
    )
    return Evidence(**{**defaults, **overrides})


def test_conflicting_series_b_amounts_detected():
    a = funding(id="a", content="Acme Robotics raised a $40M Series B.")
    b = funding(id="b", content="Acme Robotics secured $52M in its Series B round.")
    conflicts = detect_conflicts([a, b])
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert "Series B" in conflict.field
    assert set(conflict.evidence_ids) == {"a", "b"}
    assert isinstance(conflict, Conflict)


def test_amounts_within_tolerance_are_not_a_conflict():
    a = funding(content="Acme Robotics raised a $40M Series B.")
    b = funding(content="Acme Robotics raised a $42M Series B.")  # 5% apart
    assert detect_conflicts([a, b]) == []


def test_different_rounds_do_not_conflict():
    a = funding(content="Acme Robotics raised a $10M Series A.")
    b = funding(content="Acme Robotics raised a $40M Series B.")
    assert detect_conflicts([a, b]) == []


def test_non_funding_evidence_ignored():
    a = funding(category=DataCategory.NEWS, content="Acme's $40M Series B was covered.")
    b = funding(category=DataCategory.NEWS, content="Acme's $52M Series B, reporters say.")
    assert detect_conflicts([a, b]) == []


def test_single_source_never_conflicts():
    assert detect_conflicts([funding(content="Acme raised $40M in Series B.")]) == []


def test_empty_list():
    assert detect_conflicts([]) == []


def test_corpus_surfaces_series_b_conflict():
    conflicts = detect_conflicts(build_corpus())
    series_b = [c for c in conflicts if "Series B" in c.field]
    assert len(series_b) == 1
    ids = set(series_b[0].evidence_ids)
    # The $40M sources (ev02/ev03) disagree with the $52M source (ev06).
    assert "ev06" in ids
    assert ids & {"ev02", "ev03"}


def test_detect_conflicts_does_not_mutate_input():
    corpus = build_corpus()
    ids_before = [e.id for e in corpus]
    detect_conflicts(corpus)
    assert [e.id for e in corpus] == ids_before
