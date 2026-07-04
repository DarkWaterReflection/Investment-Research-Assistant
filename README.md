# Investment Research Assistant

AI-powered investment due diligence with **source attribution**. Give it a
company name; it gathers evidence from regulatory filings, the company's own
website, and web/news search, validates and scores that evidence, runs a
citation-enforced LLM analysis, and produces an investment memo in which
**every sourced claim is a numbered footnote back to the bytes it came from**
— exportable as Markdown, HTML, or PDF.

The guiding principle: an unsourced or mis-attributed fact is worse than a
missing one. Every datum is an **`Evidence`** record carrying its verbatim
payload, source URL, timestamps, and reliability score; every analytical
claim is a **`Finding`** labeled *sourced*, *inferred*, or *assumption* — and
a "sourced" claim that can't cite real evidence is downgraded, visibly, to an
inference. Facts and guesses never blur.

## How it works

```
POST /research
     │
     ▼
┌────────────┐   ┌─────────────┐   ┌────────────┐   ┌────────────┐
│ COLLECTING │──►│ VALIDATING  │──►│ ANALYZING  │──►│ GENERATING │──► memo
│ collectors/│   │ processors/ │   │ analysis/  │   │  reports/  │   (md/html/pdf)
└────────────┘   └─────────────┘   └─────┬──────┘   └────────────┘
 SEC EDGAR        clean → dedupe →       │ llm/  (Anthropic │ OpenAI │ Gemini)
 Firecrawl        entity-resolve →       │ structured output + citation
 SerpAPI          confidence →           │ enforcement, cost budget
 (auto-enable     conflicts → timeline   │
  by credential)  quarantine, never delete
```

- **`collectors/`** — one adapter per provider, all emitting `Evidence`. The
  registry auto-enables each collector when its credentials exist; keyless
  SEC EDGAR is always on. Reliability priors: SEC `0.98`, website `0.9`,
  search `0.65`. ([ADR 0001](docs/adr/0001-evidence-first-architecture.md))
- **`processors/`** — the validation pipeline: clean → dedupe →
  entity-resolve → confidence → conflicts → timeline. Off-target evidence is
  quarantined, never deleted; conflicting figures (two sizes for one funding
  round) are surfaced, never auto-resolved.
  ([ADR 0002](docs/adr/0002-data-processing-pipeline.md))
- **`llm/`** — provider-agnostic structured output over raw HTTP (no vendor
  SDKs), with schema validation (one repair retry) and **citation
  enforcement**: sourced findings must cite real evidence IDs or they are
  downgraded to inferred with a warning.
  ([ADR 0003](docs/adr/0003-llm-abstraction-and-citation-enforcement.md))
- **`analysis/`** — a declarative roster of passes (company profile, market,
  team, funding, traction, risks) plus a synthesis, run sequentially under a
  hard per-job cost budget. The risks pass sees unresolved conflicts and
  quarantine stats — source disagreement *is* risk signal.
  ([ADR 0004](docs/adr/0004-analysis-passes-and-orchestration.md))
- **`orchestration/` + `reports/`** — the job pipeline with per-stage timing;
  one failing source degrades the job to PARTIAL instead of killing it. The
  memo renders with numbered source footnotes, a data-quality section, the
  event timeline, and diagnostics.
- **`api/` + `frontend/`** — FastAPI (async jobs, Prometheus metrics) and a
  React client (submit → live stage progress → interactive memo).
  ([ADR 0005](docs/adr/0005-api-and-single-container-deployment.md))

## Quickstart

### Backend (Python 3.11+)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env               # add keys; all data-provider keys optional
uvicorn api.app:app --reload       # http://localhost:8000/docs
```

With no data-provider keys, keyless SEC EDGAR still collects. `POST /research`
needs one LLM key (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or
`GEMINI_API_KEY`) matching `LLM_PROVIDER`.

### Frontend (Node 20+)

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173 (proxies API to :8000)
```

### Docker (API + frontend + PDF export in one container)

```bash
docker compose up --build          # http://localhost:8000
```

PDF export needs WeasyPrint's native libraries; the container has them.
Bare-metal installs can add them via `pip install -e ".[pdf]"` plus the
system Pango libraries — otherwise `/report/{id}/pdf` returns 501 and
Markdown/HTML export still works.

## API

| Endpoint | Purpose |
|---|---|
| `POST /research` | Start a job (`{company, website?, aliases?, ticker?}`) → 202 + job id |
| `GET /status/{id}` | Stage timings, warnings, cost, report availability |
| `GET /report/{id}?format=markdown\|html\|json` | The memo (Markdown is canonical) |
| `GET /report/{id}/pdf` | PDF export (501 if natives absent) |
| `GET /health` | Provider/model, enabled collectors, PDF capability |
| `GET /metrics` | Prometheus text: jobs, LLM calls, tokens, cost, latency |

Interactive docs at `/docs` (OpenAPI). Job flow: 202 → poll status
(`queued → running → complete | partial | failed`) → fetch report. PARTIAL
means the memo exists but something degraded (a source failed, or the cost
budget truncated analysis) — the memo's Diagnostics section says what.

## Configuration

Everything loads from env / `.env` (`core/config.py`):

| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER`, `LLM_MODEL` | `anthropic`, `claude-sonnet-5` | `openai` / `gemini` supported |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` | — | one required for analysis |
| `FIRECRAWL_API_KEY`, `SERPAPI_API_KEY` | — | optional; enable those collectors |
| `SEC_EDGAR_USER_AGENT` | placeholder | set a real contact — SEC requires it |
| `MAX_COST_PER_JOB_USD` | `5.0` | hard per-job LLM budget |
| `COLLECTOR_TIMEOUT_SECONDS` | `90` | per-collector fence |
| `STATIC_DIR` | — | serve a built frontend at `/` (set in Docker) |

## Testing & quality bar

```bash
ruff check . && mypy && pytest     # backend: lint + strict types + tests
cd frontend && npm test            # frontend: vitest
```

- **185+ tests**, none touching a real network: collectors are respx-mocked,
  the LLM layer is exercised by a scripted `FakeLLM` (including adversarial
  cases: fabricated citations, malformed output, budget exhaustion), and API
  tests run the real app via ASGI transport.
- `mypy --strict` with the Pydantic plugin across all backend packages;
  TypeScript `strict` on the frontend.
- CI (`.github/workflows/ci.yml`): Python 3.11/3.13 matrix, frontend
  build+test, and a Docker job that builds the image and smoke-tests the
  running container.

## Deployment

- **Cloud Run** (single container: API + UI + PDF): manual GitHub Action
  **Deploy (Cloud Run)** — prerequisites documented in
  [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml). Runtime
  secrets live in GCP Secret Manager, never in GitHub.
- **Split hosting**: frontend on Vercel
  ([`frontend/vercel.json`](frontend/vercel.json), point the rewrites at your
  backend URL) + the API container anywhere.
- Operations, symptom→action triage, and rollback:
  [docs/runbooks/operations.md](docs/runbooks/operations.md).

## Project layout

```
core/            Settings + shared domain types (DataCategory, JobStage, Basis…)
collectors/      Evidence model, provider adapters, registry, retry/resilience
processors/      validation pipeline → ProcessedCorpus (dedupe, quarantine, conflicts)
llm/             provider adapters (Anthropic/OpenAI/Gemini), validation, FakeLLM
analysis/        pass roster, prompts, budget-guarded engine
orchestration/   run_research_job: collect → validate → analyze → report
reports/         ReportContext, Jinja2 memo templates (md/html), PDF export
api/             FastAPI app, job store, Prometheus metrics
frontend/        React + TypeScript client (Vite)
tests/           unit / integration / api (fixture corpus, FakeLLM, respx)
docs/adr/        architecture decision records (0001–0005)
docs/runbooks/   operations runbook
```

## Architecture decisions

1. [Evidence-first data collection](docs/adr/0001-evidence-first-architecture.md)
2. [Data-processing and validation pipeline](docs/adr/0002-data-processing-pipeline.md)
3. [LLM abstraction and citation enforcement](docs/adr/0003-llm-abstraction-and-citation-enforcement.md)
4. [Analysis passes, budgets, and orchestration](docs/adr/0004-analysis-passes-and-orchestration.md)
5. [API, job store, and single-container deployment](docs/adr/0005-api-and-single-container-deployment.md)
