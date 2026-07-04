from datetime import UTC, datetime

from corpus import build_corpus

from collectors.base import Evidence
from core.types import DataCategory
from processors.timeline import TimelineEvent, build_timeline


def make_evidence(**overrides):
    defaults = dict(
        company="Acme Robotics",
        category=DataCategory.NEWS,
        title="A headline",
        content="body",
        source_url="https://news.example/story",
        collector="serpapi",
        reliability=0.6,
    )
    return Evidence(**{**defaults, **overrides})


def _dt(year, month, day):
    return datetime(year, month, day, tzinfo=UTC)


def test_events_sorted_ascending_by_published_at():
    a = make_evidence(id="a", published_at=_dt(2024, 3, 1))
    b = make_evidence(id="b", published_at=_dt(2022, 1, 1))
    c = make_evidence(id="c", published_at=_dt(2023, 6, 15))
    timeline = build_timeline([a, b, c])
    assert [e.evidence_id for e in timeline] == ["b", "c", "a"]


def test_event_carries_evidence_fields():
    ev = make_evidence(id="x", title="Series B", category=DataCategory.FUNDING,
                       published_at=_dt(2024, 3, 15))
    (event,) = build_timeline([ev])
    assert isinstance(event, TimelineEvent)
    assert event.evidence_id == "x"
    assert event.title == "Series B"
    assert event.category is DataCategory.FUNDING
    assert event.occurred_at == _dt(2024, 3, 15)


def test_missing_published_at_falls_back_to_collected_at():
    ev = make_evidence(id="x", published_at=None)
    (event,) = build_timeline([ev])
    assert event.occurred_at == ev.collected_at


def test_published_at_takes_precedence_over_collected_at():
    ev = make_evidence(id="x", published_at=_dt(2020, 1, 1))
    (event,) = build_timeline([ev])
    assert event.occurred_at == _dt(2020, 1, 1)
    assert event.occurred_at != ev.collected_at


def test_empty_list_yields_empty_timeline():
    assert build_timeline([]) == []


def test_stable_order_for_equal_timestamps():
    ts = _dt(2024, 3, 1)
    a = make_evidence(id="a", published_at=ts)
    b = make_evidence(id="b", published_at=ts)
    assert [e.evidence_id for e in build_timeline([a, b])] == ["a", "b"]


def test_does_not_mutate_input():
    corpus = build_corpus()
    ids_before = [e.id for e in corpus]
    build_timeline(corpus)
    assert [e.id for e in corpus] == ids_before


def test_corpus_timeline_is_monotonic_and_complete():
    corpus = build_corpus()
    timeline = build_timeline(corpus)
    assert len(timeline) == len(corpus)
    times = [e.occurred_at for e in timeline]
    assert times == sorted(times)
    # The oldest published item (ev09, 2019) sorts first.
    assert timeline[0].evidence_id == "ev09"
