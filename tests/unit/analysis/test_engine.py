"""Engine behaviour against FakeLLM: pass selection, budget, degradation."""

from analysis.engine import AnalysisEngine
from collectors.base import CompanyTarget, Evidence
from core.config import Settings
from core.types import DataCategory
from llm.fake import FakeLLM
from processors.pipeline import ProcessedCorpus

TARGET = CompanyTarget(name="Acme Robotics")

SECTION_PAYLOAD = {
    "summary": "Assessment based on the evidence.",
    "findings": [
        {
            "claim": "Acme builds warehouse robots",
            "basis": "sourced",
            "evidence_ids": ["ev-web"],
            "confidence": "high",
        }
    ],
}

SYNTHESIS_PAYLOAD = {
    "executive_summary": "Acme is a promising robotics company.",
    "investment_thesis": "Automation tailwinds plus strong product.",
    "strengths": [],
    "concerns": [],
    "open_questions": ["What is churn?"],
}


def ev(category, id):
    return Evidence(
        id=id,
        company="Acme Robotics",
        category=category,
        title="Acme Robotics item",
        content="Acme Robotics detail.",
        source_url="https://example.com/item",
        collector="stub",
        reliability=0.9,
        confidence=0.8,
    )


def corpus(*evidence):
    return ProcessedCorpus(evidence=list(evidence))


def make_settings(**overrides):
    return Settings(_env_file=None, **overrides)


async def test_full_corpus_runs_all_passes_and_synthesis():
    full = corpus(
        ev(DataCategory.WEBSITE, "ev-web"),
        ev(DataCategory.NEWS, "ev-news"),
        ev(DataCategory.FOUNDERS, "ev-founders"),
        ev(DataCategory.FUNDING, "ev-funding"),
        ev(DataCategory.CUSTOMERS, "ev-customers"),
    )
    fake = FakeLLM([SECTION_PAYLOAD] * 6 + [SYNTHESIS_PAYLOAD])

    result = await AnalysisEngine(fake, make_settings()).run(TARGET, full)

    assert [s.name for s in result.sections] == [
        "company_profile",
        "market",
        "team",
        "funding",
        "traction",
        "risks",
    ]
    assert result.synthesis is not None
    assert result.synthesis.open_questions == ["What is churn?"]
    assert result.skipped_passes == []
    assert not result.budget_exhausted
    assert len(result.usage) == 7
    assert result.warnings == []


async def test_passes_without_evidence_are_skipped_without_llm_calls():
    web_only = corpus(ev(DataCategory.WEBSITE, "ev-web"))
    fake = FakeLLM([SECTION_PAYLOAD, SECTION_PAYLOAD, SYNTHESIS_PAYLOAD])

    result = await AnalysisEngine(fake, make_settings()).run(TARGET, web_only)

    assert [s.name for s in result.sections] == ["company_profile", "risks"]
    assert set(result.skipped_passes) == {"market", "team", "funding", "traction"}
    assert len(fake.calls) == 3  # skips cost nothing
    assert result.synthesis is not None


async def test_budget_exhaustion_skips_remaining_passes_and_synthesis():
    two_pass = corpus(ev(DataCategory.WEBSITE, "ev-web"), ev(DataCategory.NEWS, "ev-news"))
    fake = FakeLLM([SECTION_PAYLOAD, SECTION_PAYLOAD], cost_per_call=3.0)
    settings = make_settings(max_cost_per_job_usd=5.0)

    result = await AnalysisEngine(fake, settings).run(TARGET, two_pass)

    # company_profile ($3) and market ($6 cumulative) run; then the guard trips.
    assert [s.name for s in result.sections] == ["company_profile", "market"]
    assert result.budget_exhausted
    assert "traction" in result.skipped_passes
    assert "risks" in result.skipped_passes
    assert "synthesis" in result.skipped_passes
    assert result.synthesis is None
    assert result.total_cost_usd == 6.0
    assert any("budget exhausted" in w for w in result.warnings)


async def test_citation_downgrades_surface_on_the_section():
    web_only = corpus(ev(DataCategory.WEBSITE, "ev-web"))
    fabricated = {
        "summary": "Assessment.",
        "findings": [
            {
                "claim": "Revenue is $10M",
                "basis": "sourced",
                "evidence_ids": ["ev-invented"],
                "confidence": "high",
            }
        ],
    }
    fake = FakeLLM([fabricated, fabricated, SECTION_PAYLOAD, SYNTHESIS_PAYLOAD])

    result = await AnalysisEngine(fake, make_settings()).run(TARGET, web_only)

    profile = result.sections[0]
    assert profile.name == "company_profile"
    assert any("Downgraded to inferred" in w for w in profile.warnings)
    assert profile.analysis.findings[0].basis == "inferred"
    assert result.sections[1].warnings == []


async def test_empty_corpus_produces_no_sections_and_no_calls():
    fake = FakeLLM([])

    result = await AnalysisEngine(fake, make_settings()).run(TARGET, corpus())

    assert result.sections == []
    assert result.synthesis is None
    assert "synthesis" in result.skipped_passes
    assert len(fake.calls) == 0


async def test_evidence_used_records_what_the_model_saw():
    full = corpus(ev(DataCategory.WEBSITE, "ev-web"), ev(DataCategory.FUNDING, "ev-funding"))
    fake = FakeLLM([SECTION_PAYLOAD] * 3 + [SYNTHESIS_PAYLOAD])

    result = await AnalysisEngine(fake, make_settings()).run(TARGET, full)

    by_name = {s.name: s for s in result.sections}
    assert by_name["company_profile"].evidence_used == ["ev-web"]
    assert by_name["funding"].evidence_used == ["ev-funding"]
    assert set(by_name["risks"].evidence_used) == {"ev-web", "ev-funding"}
