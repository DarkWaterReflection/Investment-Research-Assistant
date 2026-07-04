"""Job orchestrator behaviour: stage flow, error isolation, terminal states."""

import asyncio

from collectors.base import (
    BaseCollector,
    CollectorResult,
    CompanyTarget,
    Evidence,
    RateLimitedError,
)
from core.config import Settings
from core.types import DataCategory, JobStage
from llm.fake import FakeLLM
from orchestration.jobs import run_research_job

TARGET = CompanyTarget(name="Acme Robotics")

SECTION_PAYLOAD = {
    "summary": "Assessment based on the evidence.",
    "findings": [],
}

SYNTHESIS_PAYLOAD = {
    "executive_summary": "Acme looks promising.",
    "investment_thesis": "Strong automation demand.",
    "strengths": [],
    "concerns": [],
    "open_questions": [],
}


def ev(id, content="Acme Robotics builds warehouse robots."):
    return Evidence(
        id=id,
        company="Acme Robotics",
        category=DataCategory.WEBSITE,
        title="Company page",
        content=content,
        source_url=f"https://example.com/{id}",
        collector="stub",
        reliability=0.9,
    )


class StubCollector(BaseCollector):
    categories = frozenset({DataCategory.WEBSITE})
    reliability = 0.9

    def __init__(self, name, *, evidence=(), error=None, delay=0.0):
        self.name = name
        self._evidence = list(evidence)
        self._error = error
        self._delay = delay

    async def collect(self, target):
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._error is not None:
            raise self._error
        return CollectorResult(collector=self.name, evidence=self._evidence)


def make_settings(**overrides):
    return Settings(_env_file=None, **overrides)


def website_llm():
    # website-only evidence triggers company_profile + risks + synthesis
    return FakeLLM([SECTION_PAYLOAD, SECTION_PAYLOAD, SYNTHESIS_PAYLOAD])


async def test_happy_path_completes_with_stage_records():
    collectors = [
        StubCollector("stub_a", evidence=[ev("ev-1")]),
        StubCollector(
            "stub_b",
            evidence=[ev("ev-2", content="Acme Robotics announced a new fulfillment center.")],
        ),
    ]

    result = await run_research_job(
        TARGET, provider=website_llm(), settings=make_settings(), collectors=collectors
    )

    assert result.stage is JobStage.COMPLETE
    assert [record.stage for record in result.stages] == [
        JobStage.COLLECTING,
        JobStage.VALIDATING,
        JobStage.ANALYZING,
    ]
    assert result.corpus is not None
    assert len(result.corpus.evidence) == 2
    assert result.analysis is not None
    assert result.analysis.synthesis is not None


async def test_one_failing_collector_degrades_to_partial():
    collectors = [
        StubCollector("healthy", evidence=[ev("ev-1")]),
        StubCollector("throttled", error=RateLimitedError("throttled", "429 after retries")),
    ]

    result = await run_research_job(
        TARGET, provider=website_llm(), settings=make_settings(), collectors=collectors
    )

    assert result.stage is JobStage.PARTIAL
    assert any("throttled" in w for w in result.warnings)
    assert result.analysis is not None  # healthy evidence still analyzed


async def test_hanging_collector_times_out_and_degrades():
    collectors = [
        StubCollector("healthy", evidence=[ev("ev-1")]),
        StubCollector("hanging", evidence=[ev("ev-2")], delay=5.0),
    ]
    settings = make_settings(collector_timeout_seconds=0.05)

    result = await run_research_job(
        TARGET, provider=website_llm(), settings=settings, collectors=collectors
    )

    assert result.stage is JobStage.PARTIAL
    assert any("timed out" in w for w in result.warnings)
    assert result.corpus is not None
    assert len(result.corpus.evidence) == 1


async def test_all_collectors_failing_fails_the_job():
    collectors = [
        StubCollector("a", error=RateLimitedError("a", "throttled")),
        StubCollector("b", error=RateLimitedError("b", "throttled")),
    ]
    fake = FakeLLM([])

    result = await run_research_job(
        TARGET, provider=fake, settings=make_settings(), collectors=collectors
    )

    assert result.stage is JobStage.FAILED
    assert result.corpus is None
    assert result.analysis is None
    assert len(fake.calls) == 0


async def test_fully_quarantined_corpus_fails_after_validation():
    off_target = ev("ev-off", content="Totally Different Bakery ships croissants.")
    collectors = [StubCollector("stub", evidence=[off_target])]
    fake = FakeLLM([])

    result = await run_research_job(
        TARGET, provider=fake, settings=make_settings(), collectors=collectors
    )

    assert result.stage is JobStage.FAILED
    assert [record.stage for record in result.stages] == [
        JobStage.COLLECTING,
        JobStage.VALIDATING,
    ]
    assert any("quarantined" in w for w in result.warnings)
    assert len(fake.calls) == 0


async def test_no_enabled_collectors_fails_immediately():
    result = await run_research_job(
        TARGET, provider=FakeLLM([]), settings=make_settings(), collectors=[]
    )

    assert result.stage is JobStage.FAILED
    assert any("No collectors enabled" in w for w in result.warnings)


async def test_budget_exhaustion_marks_job_partial():
    collectors = [StubCollector("stub", evidence=[ev("ev-1")])]
    fake = FakeLLM([SECTION_PAYLOAD], cost_per_call=10.0)  # blows the $5 default
    settings = make_settings(max_cost_per_job_usd=5.0)

    result = await run_research_job(
        TARGET, provider=fake, settings=settings, collectors=collectors
    )

    assert result.stage is JobStage.PARTIAL
    assert result.analysis is not None
    assert result.analysis.budget_exhausted
    assert result.total_cost_usd == 10.0
