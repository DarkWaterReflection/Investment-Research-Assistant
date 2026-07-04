# Operations runbook

How to run, watch, and fix the Investment Research Assistant in production.
Architecture background lives in the ADRs (`docs/adr/`); this document is
symptom → diagnosis → action.

## Quick facts

| Thing | Value |
|---|---|
| Serve | `uvicorn api.app:app` (container: port `$PORT`, default 8080) |
| Health | `GET /health` — provider, model, enabled collectors, PDF capability |
| Metrics | `GET /metrics` — Prometheus text |
| Job states | `queued → running → complete \| partial \| failed` |
| Cost ceiling | `MAX_COST_PER_JOB_USD` (default $5) per job, enforced pre-call |
| Job store | **In-memory** — jobs are lost on restart (ADR 0005) |

## Reading /metrics

```
ira_jobs_total{status="complete"} …   # terminal jobs by outcome
ira_llm_calls_total …                 # includes repair calls (≈7/job normal,
                                      # up to 3× on repair-heavy jobs)
ira_llm_tokens_total{direction=…} …
ira_llm_cost_usd_total …              # estimated; unknown models add $0
ira_job_duration_seconds_sum/count …  # mean = sum/count
```

Watch for: rising `partial` share (a source or the budget is degrading),
`failed` > 0 (see below), cost-per-job trending toward the ceiling
(`ira_llm_cost_usd_total` delta ÷ jobs), calls-per-job well above 7
(schema/citation repairs are firing — a provider or prompt regressed).

## Symptom → action

### POST /research returns 503 "LLM provider not configured"
The server booted without a usable key for the selected provider (by design —
ADR 0005). Set `LLM_PROVIDER` + the matching `*_API_KEY`
(in Cloud Run: attach the Secret Manager secret), restart, confirm via
`/health` (`llm_provider` non-null).

### Job ends `failed`
`GET /status/{id}` → `error` field.
- `LLMAuthError` — key revoked/expired. Rotate the secret, redeploy.
- `LLMRateLimitedError` — provider throttling persisted through retries.
  Back off submissions; if chronic, raise provider tier or switch
  `LLM_PROVIDER`.
- `Collection produced no evidence` — every collector failed or returned
  nothing. Check `warnings` for per-collector reasons; verify data-provider
  keys and outbound egress.
- `All collected evidence was quarantined` — the entity resolver thinks
  nothing matched the target. Usually a name-collision problem: resubmit
  with `website` (domain matching) and/or `ticker`, or add aliases.

### Job ends `partial`
Expected degradation, not an incident. `warnings` tells you which:
- `<collector>: timed out / rate limited / …` — one source down; memo built
  from the rest. Chronic for one collector → check its key/quota.
- `budget exhausted ($X of $Y)` — later passes skipped, memo has gaps.
  Raise `MAX_COST_PER_JOB_USD` or use a cheaper `LLM_MODEL` if routine.

### /report/{id}/pdf returns 501
WeasyPrint natives absent — normal on bare-metal Windows/macOS dev boxes,
**not** normal in the container (the image installs them; a 501 there means
the image build changed — check the runtime `apt-get` layer). Markdown/HTML
export is unaffected.

### Memo quality complaints
- Claim marked *inferred* the user expected as fact → citation enforcement
  downgraded a fabricated/uncited citation (see the Diagnostics section of
  the memo). This is the system working; the fix is better evidence, not a
  code change.
- Conflicting figures shown side by side → by design; the system never picks
  a winner (ADR 0002/0004).
- Off-target company in the memo → entity resolution false-positive; file it
  with the evidence IDs from the Sources section (each item is auditable).

### Instance restarted, jobs vanished
Known limitation (ADR 0005): the job store is in-memory. Resubmit. If this
is hurting, the fix is the persistent JobStore implementation, not a patch.

## Deploy & rollback

Deploy: GitHub → Actions → **Deploy (Cloud Run)** → run workflow (builds the
image at the current SHA, pushes to Artifact Registry, deploys `ira-api`).
Prereqs are documented at the top of `.github/workflows/deploy.yml`.

Rollback: Cloud Run keeps prior revisions —
`gcloud run services update-traffic ira-api --to-revisions=<REV>=100 --region <REGION>`
(or the console's revision list). Images are tagged by commit SHA, so any
previous SHA is redeployable.

Local prod-parity: `docker compose up --build` → http://localhost:8000
(API keys from `.env`, which is never baked into the image).

## Configuration reference

All settings load from env / `.env` (`core/config.py`). Key ones:

| Env var | Default | Effect |
|---|---|---|
| `LLM_PROVIDER` / `LLM_MODEL` | `anthropic` / `claude-sonnet-5` | analysis model |
| `ANTHROPIC_API_KEY` etc. | unset | provider credential (503 gate) |
| `FIRECRAWL_API_KEY`, `SERPAPI_API_KEY`, … | unset | collector auto-enable; SEC EDGAR always on |
| `SEC_EDGAR_USER_AGENT` | placeholder | **set to a real contact** — SEC requires it |
| `MAX_COST_PER_JOB_USD` | `5.0` | per-job LLM budget |
| `COLLECTOR_TIMEOUT_SECONDS` | `90` | per-collector fence |
| `STATIC_DIR` | unset (container: `/app/static`) | serve built frontend at `/` |
