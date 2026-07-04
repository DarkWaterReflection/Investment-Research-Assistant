from analysis.passes import PASSES
from analysis.prompts import (
    MAX_CONTENT_CHARS,
    MAX_EVIDENCE_PER_PASS,
    build_pass_prompt,
    build_synthesis_prompt,
    format_evidence,
    select_evidence,
)
from analysis.schemas import SectionAnalysis, SectionResult
from collectors.base import Evidence
from core.types import DataCategory
from llm.schemas import Finding
from processors.conflicts import Conflict


def ev(category=DataCategory.WEBSITE, *, id=None, confidence=None, reliability=0.9, content=None):
    kwargs = {"id": id} if id else {}
    return Evidence(
        company="Acme Robotics",
        category=category,
        title="Acme Robotics update",
        content=content or "Acme Robotics builds warehouse robots.",
        source_url="https://acme-robotics.example/about",
        collector="stub",
        reliability=reliability,
        confidence=confidence,
        **kwargs,
    )


RISKS_SPEC = next(spec for spec in PASSES if spec.name == "risks")
FUNDING_SPEC = next(spec for spec in PASSES if spec.name == "funding")


def test_select_evidence_filters_by_category():
    items = [ev(DataCategory.WEBSITE), ev(DataCategory.NEWS), ev(DataCategory.FUNDING)]

    selected = select_evidence(items, frozenset({DataCategory.FUNDING}))

    assert [item.category for item in selected] == [DataCategory.FUNDING]


def test_select_evidence_prefers_high_confidence_and_caps():
    items = [ev(confidence=i / 100) for i in range(MAX_EVIDENCE_PER_PASS + 10)]

    selected = select_evidence(items, frozenset({DataCategory.WEBSITE}))

    assert len(selected) == MAX_EVIDENCE_PER_PASS
    confidences = [item.confidence for item in selected]
    assert confidences == sorted(confidences, reverse=True)


def test_select_evidence_falls_back_to_reliability_when_unscored():
    low = ev(confidence=None, reliability=0.2, id="low")
    high = ev(confidence=None, reliability=0.95, id="high")

    selected = select_evidence([low, high], frozenset({DataCategory.WEBSITE}))

    assert [item.id for item in selected] == ["high", "low"]


def test_format_evidence_shows_ids_and_truncates_content():
    item = ev(id="ev-1", content="Acme Robotics " + "x" * 2000)

    text = format_evidence([item])

    assert "[ev-1]" in text
    assert "confidence=0.90" in text
    assert len(text) < MAX_CONTENT_CHARS + 300  # header + capped content only


def test_risks_prompt_includes_conflicts_and_quarantine_count():
    conflict = Conflict(
        field="funding.series_b.amount",
        values=["40,000,000", "52,000,000"],
        evidence_ids=["ev-a", "ev-b"],
        description="Series B amount disagrees across sources.",
    )

    prompt = build_pass_prompt(
        "Acme Robotics", RISKS_SPEC, [ev()], conflicts=[conflict], quarantined_count=3
    )

    assert "Series B amount disagrees" in prompt
    assert "40,000,000" in prompt
    assert "3 evidence item(s) were quarantined" in prompt


def test_non_risks_prompt_omits_conflict_block():
    prompt = build_pass_prompt("Acme Robotics", FUNDING_SPEC, [ev()], quarantined_count=3)

    assert "quarantined" not in prompt
    assert "Unresolved conflicts" not in prompt


def test_synthesis_prompt_renders_sections_and_cited_ids():
    section = SectionResult(
        name="funding",
        title="Funding & Financials",
        analysis=SectionAnalysis(
            summary="Raised a Series B.",
            findings=[
                Finding(
                    claim="Raised $40M",
                    basis="sourced",
                    evidence_ids=["ev-42"],
                    confidence="high",
                )
            ],
        ),
    )

    prompt = build_synthesis_prompt("Acme Robotics", [section])

    assert "## Funding & Financials" in prompt
    assert "Raised $40M" in prompt
    assert "ev-42" in prompt
    assert "never invent new ones" in prompt
