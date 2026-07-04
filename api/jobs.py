"""In-memory job store for research jobs.

Jobs run as asyncio tasks inside the API process. The store is process-local
by design at this phase: the interface (create/get/finish/fail/wait) is what
a Redis- or Postgres-backed implementation will replace when horizontal
scaling lands, without touching the routes.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from orchestration.jobs import ResearchJobResult


@dataclass
class Job:
    """One research job's lifecycle record."""

    id: str
    company: str
    created_at: datetime
    result: ResearchJobResult | None = None
    error: str | None = None
    task: asyncio.Task[None] | None = field(default=None, repr=False)

    @property
    def status(self) -> str:
        if self.error is not None:
            return "failed"
        if self.result is not None:
            return str(self.result.stage)
        if self.task is not None and not self.task.done():
            return "running"
        return "queued"


class JobStore:
    """Process-local registry of jobs and their running tasks."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def create(self, company: str) -> Job:
        job = Job(id=uuid.uuid4().hex, company=company, created_at=datetime.now(UTC))
        self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def finish(self, job_id: str, result: ResearchJobResult) -> None:
        self._jobs[job_id].result = result

    def fail(self, job_id: str, error: str) -> None:
        self._jobs[job_id].error = error

    async def wait(self, job_id: str) -> None:
        """Block until the job's task completes (used by tests and shutdown)."""
        job = self._jobs.get(job_id)
        if job is not None and job.task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await job.task

    async def shutdown(self) -> None:
        """Cancel still-running jobs so the server can stop cleanly."""
        for job in self._jobs.values():
            if job.task is not None and not job.task.done():
                job.task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await job.task
                if job.result is None and job.error is None:
                    job.error = "cancelled: server shutdown"
