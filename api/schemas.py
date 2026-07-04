"""Request/response models for the HTTP API — the system boundary.

Input validation happens here (Pydantic), never further in. Internal models
(Evidence, AnalysisResult, …) are not exposed directly; the report JSON view
is the ReportContext, which is already a presentation model.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class ResearchRequest(BaseModel):
    company: str = Field(min_length=1, max_length=200)
    website: HttpUrl | None = None
    aliases: list[str] = Field(default_factory=list, max_length=10)
    ticker: str | None = Field(default=None, max_length=10)


class JobCreated(BaseModel):
    job_id: str
    status: str = "queued"
    status_url: str
    report_url: str


class StageInfo(BaseModel):
    stage: str
    duration_seconds: float


class JobStatus(BaseModel):
    job_id: str
    company: str
    status: str  # queued | running | complete | partial | failed
    created_at: datetime
    stages: list[StageInfo] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    total_cost_usd: float = 0.0
    report_available: bool = False
    error: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    environment: str
    llm_provider: str | None = None
    llm_model: str | None = None
    collectors_enabled: list[str] = Field(default_factory=list)
    pdf_export_available: bool = False
