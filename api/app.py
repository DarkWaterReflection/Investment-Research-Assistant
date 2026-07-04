"""Application factory.

create_app accepts injected settings/provider/collectors so tests run the
real app against FakeLLM and stub collectors. A missing LLM key does not
prevent startup — /health and /metrics must work on a misconfigured box —
but /research returns 503 until the provider is configured.

Run locally:  uvicorn api.app:app --reload
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.jobs import JobStore
from api.metrics import Metrics
from api.routes import router
from collectors.base import BaseCollector
from collectors.registry import build_enabled
from core.config import Settings, get_settings
from llm.base import BaseLLMProvider, LLMError
from llm.factory import build_llm_provider


def create_app(
    settings: Settings | None = None,
    *,
    provider: BaseLLMProvider | None = None,
    collectors: list[BaseCollector] | None = None,
) -> FastAPI:
    app_settings = settings if settings is not None else get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        client = httpx.AsyncClient(timeout=app_settings.collector_timeout_seconds)
        app.state.settings = app_settings
        app.state.client = client
        if provider is not None:
            app.state.provider = provider
        else:
            try:
                app.state.provider = build_llm_provider(client, app_settings)
            except LLMError:
                app.state.provider = None  # /research will 503 with instructions
        app.state.collectors = collectors  # None → build_enabled per job
        enabled = collectors if collectors is not None else build_enabled(client, app_settings)
        app.state.collector_names = [collector.name for collector in enabled]
        app.state.jobs = JobStore()
        app.state.metrics = Metrics()
        yield
        await app.state.jobs.shutdown()
        await client.aclose()

    app = FastAPI(
        title="Investment Research Assistant",
        description="Automated company due diligence with source attribution.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(router)

    # Serve the built frontend when present (single-container deploys). API
    # routes are registered first, so they always win over the static mount.
    if app_settings.static_dir is not None:
        static = Path(app_settings.static_dir)
        if static.is_dir():
            app.mount("/", StaticFiles(directory=static, html=True), name="frontend")
    return app


app = create_app()
