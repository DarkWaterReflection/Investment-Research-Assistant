# 5. HTTP API, in-memory job store, and single-container deployment

- Status: Accepted
- Date: 2026-07-05
- Phases: 6–8

## Context

The pipeline (ADRs 0001–0004) needed an operational shell: an HTTP boundary
for submitting jobs and fetching memos, observability, a frontend, and a way
to ship the whole thing. Research jobs take tens of seconds to minutes, so
the API must be asynchronous; the deployment target is serverless containers
(Cloud Run), where simplicity per instance beats premature distribution.

## Decision

### Async jobs behind a swappable in-memory store

`POST /research` returns **202 + job id** immediately and runs
`run_research_job` as an asyncio task; clients poll `GET /status/{id}` (stage
timings, warnings, cost, report availability) and fetch
`GET /report/{id}?format=markdown|html|json` (or `/report/{id}/pdf`). The job
store is a **process-local dict** behind a five-method interface
(create/get/finish/fail/wait) — deliberately not Redis/Postgres yet. One
Cloud Run instance handles the current workload; the interface is the seam
where a persistent queue lands when horizontal scaling or job durability is
actually needed. *Trade-off, accepted knowingly:* jobs are lost on instance
restart, and multiple instances don't share state (Cloud Run is capped at
low max-instances accordingly).

### Boot resilient, fail the endpoint

A missing LLM key does **not** prevent startup: `/health` and `/metrics` must
work on a misconfigured box. `POST /research` returns **503** with corrective
instructions until a provider is configured. Errors map to typed statuses:
404 unknown job, 409 running/failed, 422 invalid input, **501** when PDF
export's native libraries are absent (`PdfUnavailableError`).

### Hand-rolled Prometheus metrics

`/metrics` renders Prometheus text (jobs by terminal status, LLM calls,
tokens by direction, cost USD, job-duration summary) from plain counters —
no `prometheus_client` dependency for a handful of counters, and the format
is testable as text.

### Injected dependencies; the tests run the real app

`create_app(settings, provider=, collectors=)` takes its dependencies as
arguments. API tests run the actual application — lifespan, background
tasks, static mount — against `FakeLLM` and stub collectors via
`ASGITransport` (with `asgi-lifespan`, since ASGITransport alone does not
run lifespan). No test doubles of the app itself.

### One image serves everything

A three-stage Dockerfile: Node builds the React frontend; Python installs
the backend with the `[pdf]` extra; a slim runtime adds only WeasyPrint's
native libraries. The API serves the built frontend from `STATIC_DIR`
(routes win over the static mount), so **one container = API + UI + PDF
export**, non-root, `$PORT`-aware. Split hosting stays supported
(`frontend/vercel.json` rewrites). CI builds the image and smoke-tests the
*running container* (`/health`, served frontend, `/metrics`); deployment is
a manual `workflow_dispatch` to Cloud Run via Workload Identity Federation,
with runtime secrets in GCP Secret Manager — never in GitHub.

## Consequences

- End-to-end product in one deployable artifact; local prod-parity via
  `docker compose up`.
- Job durability is the known debt: an instance restart loses in-flight and
  completed jobs. The store interface and `database_url`/`redis_url` settings
  already exist for the persistent implementation.
- Polling (1.5 s from the frontend) is simple and adequate at this scale;
  move to SSE/WebSocket only if status latency starts to matter.
- PDF works in the container even where developer machines lack GTK; the
  501 path keeps Markdown/HTML export independent of native libraries.

## References

- `api/app.py` — factory, lifespan, static mount; `api/routes.py` — endpoints
- `api/jobs.py` — `JobStore` (the persistence seam); `api/metrics.py`
- `Dockerfile`, `docker-compose.yml`, `.github/workflows/{ci,deploy}.yml`
- `frontend/` — React client (poll → render memo from `ReportContext` JSON)
