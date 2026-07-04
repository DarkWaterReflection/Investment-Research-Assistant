"""HTTP endpoints. All state lives on app.state (client, provider, jobs, metrics).

Job flow: POST /research returns 202 immediately and runs the pipeline as an
asyncio task; GET /status/{id} polls; GET /report/{id} serves the memo as
markdown (default), html or json once the job reaches a terminal stage.
"""

from __future__ import annotations

import asyncio
import importlib.util
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse

from api.jobs import Job, JobStore
from api.schemas import HealthResponse, JobCreated, JobStatus, ResearchRequest, StageInfo
from collectors.base import CompanyTarget
from orchestration.jobs import ResearchJobResult, run_research_job
from reports.context import ReportContext, build_report_context
from reports.pdf import PdfUnavailableError, render_pdf
from reports.render import render_html

router = APIRouter()


@router.post("/research", status_code=202, response_model=JobCreated)
async def start_research(payload: ResearchRequest, request: Request) -> JobCreated:
    state = request.app.state
    if state.provider is None:
        raise HTTPException(
            status_code=503,
            detail="LLM provider not configured; set the API key for the selected "
            "llm_provider and restart.",
        )
    job = state.jobs.create(payload.company)
    target = CompanyTarget(
        name=payload.company,
        website=payload.website,
        aliases=payload.aliases,
        ticker=payload.ticker,
    )
    job.task = asyncio.create_task(_execute(state, job, target))
    return JobCreated(
        job_id=job.id, status_url=f"/status/{job.id}", report_url=f"/report/{job.id}"
    )


async def _execute(state: Any, job: Job, target: CompanyTarget) -> None:
    try:
        result = await run_research_job(
            target,
            provider=state.provider,
            settings=state.settings,
            client=state.client,
            collectors=state.collectors,
        )
    except Exception as exc:  # infra failures (auth, rate limit, provider down)
        state.jobs.fail(job.id, f"{type(exc).__name__}: {exc}")
        state.metrics.record_error()
    else:
        state.jobs.finish(job.id, result)
        state.metrics.record_result(result)


@router.get("/status/{job_id}", response_model=JobStatus)
async def job_status(job_id: str, request: Request) -> JobStatus:
    job = _get_job(request, job_id)
    result = job.result
    return JobStatus(
        job_id=job.id,
        company=job.company,
        status=job.status,
        created_at=job.created_at,
        stages=[
            StageInfo(stage=str(record.stage), duration_seconds=record.duration_seconds)
            for record in (result.stages if result else [])
        ],
        warnings=list(result.warnings) if result else [],
        total_cost_usd=result.total_cost_usd if result else 0.0,
        report_available=bool(result and result.report_markdown),
        error=job.error,
    )


@router.get("/report/{job_id}")
async def get_report(
    job_id: str,
    request: Request,
    format: Literal["markdown", "html", "json"] = "markdown",
) -> Response:
    result = _get_finished_result(request, job_id)
    if format == "markdown":
        assert result.report_markdown is not None  # guaranteed by _get_finished_result
        return PlainTextResponse(result.report_markdown, media_type="text/markdown")
    context = _report_context(result)
    if format == "html":
        return HTMLResponse(render_html(context))
    return Response(context.model_dump_json(), media_type="application/json")


@router.get("/report/{job_id}/pdf")
async def get_report_pdf(job_id: str, request: Request) -> Response:
    result = _get_finished_result(request, job_id)
    try:
        pdf = render_pdf(_report_context(result))
    except PdfUnavailableError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    filename = f"{result.target.name.replace(' ', '_')}_memo.pdf"
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    state = request.app.state
    return HealthResponse(
        environment=state.settings.environment,
        llm_provider=state.provider.name if state.provider else None,
        llm_model=state.provider.model if state.provider else None,
        collectors_enabled=state.collector_names,
        pdf_export_available=importlib.util.find_spec("weasyprint") is not None,
    )


@router.get("/metrics")
async def metrics(request: Request) -> PlainTextResponse:
    return PlainTextResponse(
        request.app.state.metrics.render(), media_type="text/plain; version=0.0.4"
    )


def _get_job(request: Request, job_id: str) -> Job:
    store: JobStore = request.app.state.jobs
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job id {job_id!r}.")
    return job


def _get_finished_result(request: Request, job_id: str) -> ResearchJobResult:
    job = _get_job(request, job_id)
    if job.error is not None:
        raise HTTPException(status_code=409, detail=f"Job failed: {job.error}")
    if job.result is None:
        raise HTTPException(
            status_code=409, detail=f"Job is still {job.status}; poll /status/{job_id}."
        )
    if job.result.report_markdown is None:
        raise HTTPException(
            status_code=409,
            detail="Job produced no report: " + "; ".join(job.result.warnings[-3:]),
        )
    return job.result


def _report_context(result: ResearchJobResult) -> ReportContext:
    assert result.corpus is not None and result.analysis is not None
    return build_report_context(
        company=result.target.name,
        corpus=result.corpus,
        analysis=result.analysis,
        stage=str(result.stage),
        total_cost_usd=result.total_cost_usd,
        warnings=result.warnings,
    )
