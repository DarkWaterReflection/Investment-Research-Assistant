from datetime import UTC, datetime

import pytest

from analysis.schemas import (
    AnalysisResult,
    MemoSynthesis,
    SectionAnalysis,
    SectionResult,
)
from collectors.base import Evidence
from core.types import DataCategory
from llm.schemas import Finding
from processors.conflicts import Conflict
from processors.pipeline import ProcessedCorpus
from processors.timeline import TimelineEvent
from reports.context import build_report_context


def make_evidence(id, title, url, published=None):
    return Evidence(
        id=id,
        company="Acme Robotics",
        category=DataCategory.NEWS,
        title=title,
        content="Acme Robotics detail.",
        source_url=url,
        collector="serpapi",
        reliability=0.65,
        published_at=published,
    )


def finding(claim, ids, basis="sourced", confidence="high"):
    return Finding(claim=claim, basis=basis, evidence_ids=ids, confidence=confidence)


@pytest.fixture
def corpus():
    ev1 = make_evidence(
        "ev-1",
        "Acme raises $40M Series B",
        "https://news.example/acme-40m",
        published=datetime(2026, 6, 30, tzinfo=UTC),
    )
    ev2 = make_evidence(
        "ev-2",
        "Acme opens Berlin office",
        "https://news.example/acme-berlin",
        published=datetime(2026, 5, 12, tzinfo=UTC),
    )
    return ProcessedCorpus(
        evidence=[ev1, ev2],
        quarantined=[make_evidence("ev-q", "Acme Bakery pie sale", "https://pies.example/x")],
        merged=[("ev-dup", "ev-1")],
        conflicts=[
            Conflict(
                field="funding.series_b.amount",
                values=["40,000,000", "52,000,000"],
                evidence_ids=["ev-1", "ev-2"],
                description="Series B amount disagrees across sources.",
            )
        ],
        timeline=[
            TimelineEvent(
                occurred_at=datetime(2026, 5, 12, tzinfo=UTC),
                title="Acme opens Berlin office",
                evidence_id="ev-2",
                category=DataCategory.NEWS,
            )
        ],
    )


@pytest.fixture
def analysis():
    return AnalysisResult(
        sections=[
            SectionResult(
                name="funding",
                title="Funding & Financials",
                analysis=SectionAnalysis(
                    summary="Raised a contested Series B.",
                    findings=[
                        finding("Raised $40M Series B", ["ev-1"]),
                        finding("Round size is disputed", ["ev-1", "ev-2"]),
                        finding("Probably raising again soon", [], basis="inferred"),
                    ],
                ),
                warnings=["Dropped unknown evidence ids ['ev-ghost'] from claim 'x'."],
            )
        ],
        synthesis=MemoSynthesis(
            executive_summary="Acme is a fast-growing robotics company.",
            investment_thesis="Automation demand is durable.",
            strengths=[finding("European expansion underway", ["ev-2"])],
            concerns=[finding("Funding figures conflict", ["ev-1", "ev-ghost"])],
            open_questions=["What is the real Series B size?"],
        ),
        total_cost_usd=0.42,
    )


@pytest.fixture
def context(corpus, analysis):
    return build_report_context(
        company="Acme Robotics",
        corpus=corpus,
        analysis=analysis,
        stage="complete",
        total_cost_usd=0.42,
        warnings=["serpapi: no news results"],
        generated_at=datetime(2026, 7, 4, 12, 0, tzinfo=UTC),
    )
