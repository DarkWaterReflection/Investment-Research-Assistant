import pytest
from corpus import build_corpus, build_target

from collectors.base import CompanyTarget, Evidence
from core.types import DataCategory
from processors.pipeline import ProcessedCorpus, ValidationPipeline


def make_evidence(**overrides):
    defaults = dict(
        company="Acme Robotics",
        category=DataCategory.NEWS,
        title="A headline",
        content="Acme Robotics did a thing.",
        source_url="https://news.example/story",
        collector="serpapi",
        reliability=0.6,
    )
    return Evidence(**{**defaults, **overrides})


@pytest.fixture
def processed() -> ProcessedCorpus:
    return ValidationPipeline().run(build_corpus(), build_target())


def test_run_returns_processed_corpus(processed):
    assert isinstance(processed, ProcessedCorpus)


def test_duplicates_are_merged_and_dropped(processed):
    kept_ids = {e.id for e in processed.evidence}
    assert "ev03" not in kept_ids
    assert "ev05" not in kept_ids
    assert ("ev03", "ev02") in processed.merged
    assert ("ev05", "ev04") in processed.merged


def test_off_target_item_is_quarantined(processed):
    quarantined_ids = {e.id for e in processed.quarantined}
    assert "ev07" in quarantined_ids
    assert "ev07" not in {e.id for e in processed.evidence}


def test_series_b_conflict_is_detected(processed):
    assert any("Series B" in c.field for c in processed.conflicts)


def test_conflict_produces_a_warning(processed):
    assert processed.warnings
    assert any("conflict" in w.lower() for w in processed.warnings)


def test_all_evidence_has_confidence_in_unit_interval(processed):
    assert processed.evidence
    for item in processed.evidence:
        assert item.confidence is not None
        assert 0.0 <= item.confidence <= 1.0


def test_timeline_covers_all_kept_evidence_and_is_sorted(processed):
    assert len(processed.timeline) == len(processed.evidence)
    times = [event.occurred_at for event in processed.timeline]
    assert times == sorted(times)


def test_content_is_cleaned_of_html(processed):
    by_id = {e.id: e for e in processed.evidence}
    # ev11's raw content was wrapped in <div>...</div>.
    assert "<" not in by_id["ev11"].content
    assert "<" not in by_id["ev11"].title


def test_pipeline_does_not_mutate_input():
    corpus = build_corpus()
    ids_before = [e.id for e in corpus]
    ValidationPipeline().run(corpus, build_target())
    assert [e.id for e in corpus] == ids_before
    assert all(item.confidence is None for item in corpus)  # scored on copies


def test_empty_evidence_yields_empty_corpus():
    result = ValidationPipeline().run([], build_target())
    assert result.evidence == []
    assert result.quarantined == []
    assert result.merged == []
    assert result.conflicts == []
    assert result.timeline == []
    assert result.warnings == []


def test_heavy_quarantine_raises_warning():
    target = CompanyTarget(name="Acme Robotics", website="https://acme-robotics.example")
    # Four off-target items, one on-target -> 80% quarantined (> 30%).
    # Distinct content so dedupe does not collapse them before resolution.
    off_topics = ["Globex earnings", "Initech layoffs", "Umbrella recall", "Soylent merger"]
    off = [
        make_evidence(id=f"off{i}", company="Other",
                      content=f"Unrelated report about {topic} this week.",
                      source_url=f"https://elsewhere.example/{i}")
        for i, topic in enumerate(off_topics)
    ]
    on = [make_evidence(id="on", content="Acme Robotics shipped a product.")]
    result = ValidationPipeline().run(off + on, target)
    assert len(result.quarantined) == 4
    assert any("quarantined" in w.lower() for w in result.warnings)
