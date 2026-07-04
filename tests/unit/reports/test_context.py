"""Context builder: footnote numbering, dead-ref handling, stats mapping."""

from analysis.schemas import AnalysisResult
from reports.context import build_report_context


def test_footnotes_numbered_in_reading_order_synthesis_first(context):
    # Synthesis strengths cite ev-2 before any section cites ev-1.
    assert context.strengths[0].citations == [1]
    assert context.sections[0].findings[0].citations == [2]


def test_repeated_citations_reuse_the_same_number(context):
    disputed = context.sections[0].findings[1]

    assert disputed.citations == [2, 1]  # ev-1 already #2, ev-2 already #1
    assert len(context.sources) == 2  # two evidence items, two register entries


def test_unknown_evidence_ids_never_render(context):
    concern = context.concerns[0]

    assert concern.citations == [2]  # ev-ghost silently dropped
    assert all(source.evidence_id != "ev-ghost" for source in context.sources)


def test_source_register_carries_url_collector_and_date(context):
    first = context.sources[0]

    assert first.evidence_id == "ev-2"
    assert first.url == "https://news.example/acme-berlin"
    assert first.collector == "serpapi"
    assert first.published == "2026-05-12"


def test_stats_conflicts_and_timeline_are_mapped(context):
    assert context.stats.evidence_count == 2
    assert context.stats.quarantined_count == 1
    assert context.stats.merged_count == 1
    assert context.stats.conflict_count == 1
    assert context.stats.total_cost_usd == 0.42
    assert context.conflicts == ["Series B amount disagrees across sources."]
    assert context.timeline[0].date == "2026-05-12"


def test_inferred_findings_carry_no_citations(context):
    inferred = context.sections[0].findings[2]

    assert inferred.basis == "inferred"
    assert inferred.citations == []


def test_missing_synthesis_leaves_memo_head_empty(corpus):
    analysis = AnalysisResult()  # no sections, no synthesis

    context = build_report_context(
        company="Acme Robotics",
        corpus=corpus,
        analysis=analysis,
        stage="partial",
        total_cost_usd=0.0,
    )

    assert context.executive_summary is None
    assert context.investment_thesis is None
    assert context.strengths == []
    assert context.open_questions == []
    assert context.sources == []
