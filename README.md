# Investment Research Assistant

AI-powered investment due diligence with **source attribution**. Given a company,
the platform gathers evidence from regulatory filings, the company's own website,
and web/news search, then cleans, deduplicates, and scores that evidence so every
downstream claim can be traced back to the bytes it came from and weighed by how
much to trust it.

The guiding principle: an unsourced or mis-attributed fact is worse than a missing
one. Every datum is an **`Evidence`** record carrying its verbatim source payload,
source URL, timestamps, and a reliability score — see
[ADR 0001](docs/adr/0001-evidence-first-architecture.md).

## Status

Early development. Built and tested so far:

| Phase | Scope | State |
|-------|-------|-------|
| 0 / 1 | Evidence model + collector adapters (SEC EDGAR, Firecrawl, SerpAPI), credential-driven registry, typed errors, retry/resilience | Done |
| 2 | Data-processing pipeline: cleaning, dedupe, entity resolution, rule-based NER, reliability scoring, conflict surfacing, timeline | In progress |

Everything below Phase 2 is **roadmap, not built** — see [Roadmap](#roadmap).

## Architecture

```
                 built ─────────────────┐   ┌──────────── roadmap ────────────┐
  collectors/  ───►  processors/  ───►   │   │  llm + analysis  ───►  reports  ───►  api + frontend
  (evidence)        (validation)         │   │
```

- **`collectors/`** — one adapter per data provider, all emitting the same
  `Evidence` records. A registry auto-enables each collector when its credentials
  are present (SEC EDGAR needs none and is always on). Reliability priors: SEC
  EDGAR `0.98`, Firecrawl website `0.9`, SerpAPI web/news `0.65`.
- **`processors/`** — the `ValidationPipeline`: clean → dedupe → entity-resolve →
  confidence → conflicts → timeline, producing a `ProcessedCorpus`. Transforms are
  immutable (raw payloads are never mutated), entity mismatches are quarantined
  rather than deleted, and source conflicts are surfaced rather than auto-resolved.
  See [ADR 0002](docs/adr/0002-data-processing-pipeline.md).
- **`core/`** — shared config (`Settings`, loaded from env/`.env`) and domain types
  (`DataCategory`, `JobStage`, `Basis`, `Confidence`).

## Quickstart

Requires Python 3.11+.

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install the package with dev dependencies
pip install -e ".[dev]"

# 3. Configure credentials (all data-provider keys are optional)
cp .env.example .env             # then edit .env

# 4. Run the test suite
pytest
```

Collectors auto-enable based on which keys are set in `.env`. With no keys at all,
the keyless SEC EDGAR collector still runs — the system degrades gracefully rather
than requiring a full key set.

## Project layout

```
core/                 config (Settings) and shared domain types
collectors/           provider adapters + Evidence model, registry, resilience
  base.py             Evidence, CompanyTarget, CollectorResult, BaseCollector, errors
  registry.py         credential-driven collector enablement
  resilience.py       retry with exponential backoff
  sec_edgar.py        SEC EDGAR (keyless, reliability 0.98)
  firecrawl.py        company website → markdown (0.9)
  serpapi.py          web + news search verticals (0.65)
processors/           validation pipeline (Phase 2)
tests/
  unit/               evidence model, registry
  integration/        respx-mocked collector tests
docs/adr/             architecture decision records
```

## Quality bar

- **Lint:** `ruff check .` (pycodestyle, pyflakes, isort, pyupgrade, bugbear,
  simplify, and type-annotation rules).
- **Types:** `mypy` in `--strict` mode with the Pydantic plugin.
- **Tests:** `pytest`, with `pytest-asyncio` and `respx` for mocking HTTP.
- **No live calls in CI.** External-API tests are marked `live` and excluded by
  default (`addopts = -m 'not live'`); CI never hits real provider endpoints.
- **CI** runs lint, type-check, and tests on Python 3.11 and 3.13
  (`.github/workflows/ci.yml`).

Run the full bar locally:

```bash
ruff check . && mypy && pytest
```

## Roadmap

Planned, not yet implemented:

- **LLM + analysis** — reason over the processed corpus, producing claims tagged
  with `Basis` (sourced / inferred / assumption) and `Confidence`.
- **Reports** — generate due-diligence reports with inline source attribution.
- **API + frontend** — job submission, async processing (Redis-backed queue),
  and a UI for browsing evidence and reports.

## Architecture decisions

- [ADR 0001 — Evidence-first data collection architecture](docs/adr/0001-evidence-first-architecture.md)
- [ADR 0002 — Data-processing and validation pipeline](docs/adr/0002-data-processing-pipeline.md)
