"""End-to-end API tests: the real app against FakeLLM and stub collectors."""

import asyncio
import sys
from contextlib import asynccontextmanager

from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from api.app import create_app
from collectors.base import BaseCollector, CollectorResult, Evidence
from core.config import Settings
from core.types import DataCategory
from llm.base import BaseLLMProvider, LLMAuthError
from llm.fake import FakeLLM

SECTION_PAYLOAD = {"summary": "Assessment based on the evidence.", "findings": []}
SYNTHESIS_PAYLOAD = {
    "executive_summary": "Acme looks promising.",
    "investment_thesis": "Strong automation demand.",
    "strengths": [],
    "concerns": [],
    "open_questions": [],
}


class StubCollector(BaseCollector):
    name = "stub"
    categories = frozenset({DataCategory.WEBSITE})
    reliability = 0.9

    def __init__(self):
        self._evidence = [
            Evidence(
                id="ev-1",
                company="Acme Robotics",
                category=DataCategory.WEBSITE,
                title="Company page",
                content="Acme Robotics builds warehouse robots.",
                source_url="https://example.com/about",
                collector="stub",
                reliability=0.9,
            )
        ]

    async def collect(self, target):
        return CollectorResult(collector=self.name, evidence=self._evidence)


class GatedProvider(BaseLLMProvider):
    """Blocks every completion until the gate opens — lets tests observe 'running'."""

    name = "gated"
    model = "fake-1"

    def __init__(self, inner, gate):
        self._inner = inner
        self._gate = gate

    async def complete_structured(self, *, system, prompt, schema, max_tokens=4096):
        await self._gate.wait()
        return await self._inner.complete_structured(
            system=system, prompt=prompt, schema=schema, max_tokens=max_tokens
        )


class FailingProvider(BaseLLMProvider):
    name = "failing"
    model = "fake-1"

    async def complete_structured(self, *, system, prompt, schema, max_tokens=4096):
        raise LLMAuthError(self.name, "key revoked")


def website_llm():
    # website-only evidence triggers company_profile + risks + synthesis
    return FakeLLM([SECTION_PAYLOAD, SECTION_PAYLOAD, SYNTHESIS_PAYLOAD])


@asynccontextmanager
async def running_app(settings=None, **kwargs):
    kwargs.setdefault("collectors", [StubCollector()])
    app = create_app(settings if settings is not None else Settings(_env_file=None), **kwargs)
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield app, client


async def start_job(client, company="Acme Robotics"):
    response = await client.post("/research", json={"company": company})
    assert response.status_code == 202
    return response.json()["job_id"]


async def test_full_research_flow_markdown_html_json():
    async with running_app(provider=website_llm()) as (app, client):
        job_id = await start_job(client)
        await app.state.jobs.wait(job_id)

        status = (await client.get(f"/status/{job_id}")).json()
        assert status["status"] == "complete"
        assert status["report_available"] is True
        assert [s["stage"] for s in status["stages"]] == [
            "collecting",
            "validating",
            "analyzing",
            "generating",
        ]

        markdown = await client.get(f"/report/{job_id}")
        assert markdown.status_code == 200
        assert markdown.headers["content-type"].startswith("text/markdown")
        assert "# Investment Memo — Acme Robotics" in markdown.text

        html = await client.get(f"/report/{job_id}", params={"format": "html"})
        assert html.status_code == 200
        assert "<h1>Investment Memo — Acme Robotics</h1>" in html.text

        json_report = await client.get(f"/report/{job_id}", params={"format": "json"})
        assert json_report.status_code == 200
        assert json_report.json()["company"] == "Acme Robotics"


async def test_report_returns_409_until_job_finishes():
    gate = asyncio.Event()
    async with running_app(provider=GatedProvider(website_llm(), gate)) as (app, client):
        job_id = await start_job(client)

        early = await client.get(f"/report/{job_id}")
        assert early.status_code == 409
        assert "poll /status/" in early.json()["detail"]

        gate.set()
        await app.state.jobs.wait(job_id)
        done = await client.get(f"/report/{job_id}")
        assert done.status_code == 200


async def test_unknown_job_is_404():
    async with running_app(provider=website_llm()) as (_, client):
        assert (await client.get("/status/nope")).status_code == 404
        assert (await client.get("/report/nope")).status_code == 404
        assert (await client.get("/report/nope/pdf")).status_code == 404


async def test_research_without_configured_provider_is_503():
    # No API keys in settings → factory cannot build a provider at startup.
    async with running_app(provider=None) as (_, client):
        response = await client.post("/research", json={"company": "Acme Robotics"})

        assert response.status_code == 503
        assert "LLM provider not configured" in response.json()["detail"]


async def test_infrastructure_failure_marks_job_failed():
    async with running_app(provider=FailingProvider()) as (app, client):
        job_id = await start_job(client)
        await app.state.jobs.wait(job_id)

        status = (await client.get(f"/status/{job_id}")).json()
        assert status["status"] == "failed"
        assert "LLMAuthError" in status["error"]

        report = await client.get(f"/report/{job_id}")
        assert report.status_code == 409
        assert "Job failed" in report.json()["detail"]


async def test_invalid_request_body_is_422():
    async with running_app(provider=website_llm()) as (_, client):
        assert (await client.post("/research", json={"company": ""})).status_code == 422
        assert (await client.post("/research", json={})).status_code == 422


async def test_health_reports_configuration():
    async with running_app(provider=website_llm()) as (_, client):
        body = (await client.get("/health")).json()

        assert body["status"] == "ok"
        assert body["llm_provider"] == "fake"
        assert body["llm_model"] == "fake-1"
        assert body["collectors_enabled"] == ["stub"]
        assert isinstance(body["pdf_export_available"], bool)


async def test_metrics_expose_job_and_token_counters():
    async with running_app(provider=website_llm()) as (app, client):
        job_id = await start_job(client)
        await app.state.jobs.wait(job_id)

        text = (await client.get("/metrics")).text

        assert 'ira_jobs_total{status="complete"} 1' in text
        assert "ira_llm_calls_total 3" in text
        assert 'ira_llm_tokens_total{direction="input"} 300' in text
        assert "ira_job_duration_seconds_count 1" in text


async def test_serves_frontend_when_static_dir_configured(tmp_path):
    (tmp_path / "index.html").write_text("<html><body>IRA frontend</body></html>")
    settings = Settings(_env_file=None, static_dir=str(tmp_path))

    async with running_app(settings=settings, provider=website_llm()) as (_, client):
        page = await client.get("/")
        assert page.status_code == 200
        assert "IRA frontend" in page.text
        # API routes are registered before the mount and always win.
        assert (await client.get("/health")).status_code == 200


async def test_root_is_404_without_static_dir():
    async with running_app(provider=website_llm()) as (_, client):
        assert (await client.get("/")).status_code == 404


async def test_pdf_export_returns_501_without_weasyprint(monkeypatch):
    monkeypatch.setitem(sys.modules, "weasyprint", None)
    async with running_app(provider=website_llm()) as (app, client):
        job_id = await start_job(client)
        await app.state.jobs.wait(job_id)

        response = await client.get(f"/report/{job_id}/pdf")

        assert response.status_code == 501
        assert "pip install" in response.json()["detail"]
