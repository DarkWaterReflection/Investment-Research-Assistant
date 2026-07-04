import pytest
from corpus import build_corpus

from collectors.base import Evidence
from core.types import DataCategory
from processors.dedupe import DedupeResult, canonicalize_url, dedupe_evidence


def make_evidence(**overrides):
    defaults = dict(
        company="Acme Robotics",
        category=DataCategory.NEWS,
        title="Acme raises Series B",
        content="Acme Robotics announced a $40M Series B.",
        source_url="https://news.example/acme-series-b",
        collector="serpapi",
        reliability=0.65,
    )
    return Evidence(**{**defaults, **overrides})


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://News.Example/Path", "https://news.example/Path"),
        ("https://news.example/path/", "https://news.example/path"),
        ("https://news.example/path#section", "https://news.example/path"),
        ("https://news.example/a?utm_source=x&utm_medium=y", "https://news.example/a"),
        ("https://news.example/a?gclid=123&fbclid=456&ref=nl", "https://news.example/a"),
        ("https://news.example/a?utm_source=x&id=7", "https://news.example/a?id=7"),
        ("https://news.example/", "https://news.example/"),
    ],
)
def test_canonicalize_url(raw, expected):
    assert canonicalize_url(raw) == expected


def test_canonicalize_url_is_idempotent():
    once = canonicalize_url("https://News.Example/p/?utm_source=x#frag")
    assert canonicalize_url(once) == once


def test_same_url_differing_only_by_tracking_params_are_duplicates():
    a = make_evidence(source_url="https://news.example/story?utm_source=twitter", reliability=0.7)
    b = make_evidence(source_url="https://news.example/story?utm_campaign=daily", reliability=0.5)
    result = dedupe_evidence([a, b])
    assert len(result.kept) == 1
    assert result.kept[0].id == a.id  # higher reliability wins
    assert result.merged == [(b.id, a.id)]


def test_near_identical_content_are_duplicates():
    base = "Acme Robotics closed a Series B round to expand manufacturing across the country."
    a = make_evidence(source_url="https://one.example/x", content=base, reliability=0.6)
    b = make_evidence(
        source_url="https://two.example/y",
        content=base + " today",
        reliability=0.8,
    )
    result = dedupe_evidence([a, b])
    assert len(result.kept) == 1
    assert result.kept[0].id == b.id  # higher reliability wins
    assert result.merged == [(a.id, b.id)]


def test_distinct_content_and_urls_are_not_merged():
    a = make_evidence(source_url="https://one.example/x", content="Wholly unrelated alpha topic.")
    b = make_evidence(source_url="https://two.example/y", content="Totally different beta subject.")
    result = dedupe_evidence([a, b])
    assert len(result.kept) == 2
    assert result.merged == []


def test_dedupe_empty_list():
    result = dedupe_evidence([])
    assert result == DedupeResult(kept=[], merged=[])


def test_dedupe_does_not_mutate_input_order_or_items():
    evidence = build_corpus()
    ids_before = [e.id for e in evidence]
    dedupe_evidence(evidence)
    assert [e.id for e in evidence] == ids_before


def test_dedupe_on_corpus_collapses_known_duplicates():
    result = dedupe_evidence(build_corpus())
    kept_ids = {e.id for e in result.kept}
    # ev03 is an exact-URL dupe of ev02; ev05 is a near-dupe of ev04.
    assert "ev03" not in kept_ids
    assert "ev05" not in kept_ids
    assert {"ev02", "ev04"} <= kept_ids
    assert ("ev03", "ev02") in result.merged
    assert ("ev05", "ev04") in result.merged
    # 15 records, 2 dropped as duplicates.
    assert len(result.kept) == 13
