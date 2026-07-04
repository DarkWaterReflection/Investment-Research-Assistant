"""End-to-end research job orchestration: collect → validate → analyze → report.

One failing collector never fails the job — its error becomes a warning and
the job degrades to PARTIAL. The job FAILS only when there is nothing to
analyze: no collectors enabled, no evidence collected, or everything
quarantined as off-target. GENERATING renders the canonical Markdown memo;
HTML/PDF exports are derived on demand from the same ReportContext.
"""

from __future__ import annotations

import asyncio
import time

import httpx
from pydantic import BaseModel, Field

from analysis.engine import AnalysisEngine
from analysis.schemas import AnalysisResult
from collectors.base import (
    BaseCollector,
    CollectorError,
    CollectorResult,
    CompanyTarget,
    Evidence,
)
from collectors.registry import build_enabled
from core.config import Settings
from core.types import JobStage
from llm.base import BaseLLMProvider
from processors.pipeline import ProcessedCorpus, ValidationPipeline
from reports.context import build_report_context
from reports.render import render_markdown


class StageRecord(BaseModel):
    """Timing record for one completed pipeline stage."""

    stage: JobStage
    duration_seconds: float = Field(ge=0.0)


class ResearchJobResult(BaseModel):
    """Everything one research job produced, including its diagnostics."""

    target: CompanyTarget
    stage: JobStage  # terminal: COMPLETE, PARTIAL or FAILED
    stages: list[StageRecord] = Field(default_factory=list)
    collector_results: list[CollectorResult] = Field(default_factory=list)
    corpus: ProcessedCorpus | None = None
    analysis: AnalysisResult | None = None
    report_markdown: str | None = None
    warnings: list[str] = Field(default_factory=list)
    total_cost_usd: float = 0.0


async def _collect_one(
    collector: BaseCollector, target: CompanyTarget, timeout: float
) -> CollectorResult | str:
    """Run one collector; failures come back as a warning string, never raise."""
    try:
        return await asyncio.wait_for(collector.collect(target), timeout=timeout)
    except TimeoutError:
        return f"{collector.name}: timed out after {timeout:.0f}s"
    except CollectorError as exc:
        return f"{collector.name}: {exc}"


async def run_research_job(
    target: CompanyTarget,
    *,
    provider: BaseLLMProvider,
    settings: Settings,
    client: httpx.AsyncClient | None = None,
    collectors: list[BaseCollector] | None = None,
) -> ResearchJobResult:
    """Run the full pipeline for one company. Never raises for data problems."""
    result = ResearchJobResult(target=target, stage=JobStage.QUEUED)
    if collectors is None:
        if client is None:
            raise ValueError("run_research_job needs either collectors or an http client")
        collectors = build_enabled(client, settings)
    if not collectors:
        result.stage = JobStage.FAILED
        result.warnings.append("No collectors enabled; check provider credentials.")
        return result

    # --- COLLECTING: all collectors concurrently, each individually fenced ---
    start = time.perf_counter()
    outcomes = await asyncio.gather(
        *(_collect_one(c, target, settings.collector_timeout_seconds) for c in collectors)
    )
    evidence: list[Evidence] = []
    collector_failures = 0
    for outcome in outcomes:
        if isinstance(outcome, str):
            collector_failures += 1
            result.warnings.append(outcome)
            continue
        result.collector_results.append(outcome)
        result.warnings.extend(f"{outcome.collector}: {w}" for w in outcome.warnings)
        evidence.extend(outcome.evidence)
    result.stages.append(
        StageRecord(stage=JobStage.COLLECTING, duration_seconds=time.perf_counter() - start)
    )
    if not evidence:
        result.stage = JobStage.FAILED
        result.warnings.append("Collection produced no evidence.")
        return result

    # --- VALIDATING ---
    start = time.perf_counter()
    corpus = ValidationPipeline().run(evidence, target)
    result.corpus = corpus
    result.warnings.extend(corpus.warnings)
    result.stages.append(
        StageRecord(stage=JobStage.VALIDATING, duration_seconds=time.perf_counter() - start)
    )
    if not corpus.evidence:
        result.stage = JobStage.FAILED
        result.warnings.append("All collected evidence was quarantined as off-target.")
        return result

    # --- ANALYZING ---
    start = time.perf_counter()
    analysis: AnalysisResult = await AnalysisEngine(provider, settings).run(target, corpus)
    result.analysis = analysis
    result.total_cost_usd = analysis.total_cost_usd
    result.stages.append(
        StageRecord(stage=JobStage.ANALYZING, duration_seconds=time.perf_counter() - start)
    )

    degraded = collector_failures > 0 or analysis.budget_exhausted
    result.stage = JobStage.PARTIAL if degraded else JobStage.COMPLETE

    # --- GENERATING: render the canonical Markdown memo ---
    start = time.perf_counter()
    context = build_report_context(
        company=target.name,
        corpus=corpus,
        analysis=analysis,
        stage=str(result.stage),
        total_cost_usd=result.total_cost_usd,
        warnings=result.warnings,
    )
    result.report_markdown = render_markdown(context)
    result.stages.append(
        StageRecord(stage=JobStage.GENERATING, duration_seconds=time.perf_counter() - start)
    )
    return result
