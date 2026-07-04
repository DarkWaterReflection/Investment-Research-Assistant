# 1. Evidence-first data collection architecture

- Status: Accepted
- Date: 2026-07-04
- Phase: 0 / 1 (commit `0c3fcc5`)

## Context

The platform produces investment due-diligence reports. In that domain an
unsourced or mis-attributed claim is worse than a missing one: a human analyst
must be able to trace every statement back to the bytes it came from, and a
reader must be able to weigh how much to trust each fact. Two failure modes
dominate automated research tools:

1. **Provenance loss** — data is scraped, transformed, and summarized until the
   original source is no longer recoverable, so nothing can be audited or
   re-verified.
2. **Uniform trust** — a promotional line from a company's own homepage is
   treated with the same weight as an SEC filing, because the pipeline carries
   no notion of source reliability.

We also need to integrate many heterogeneous providers (regulatory filings,
website scraping, web/news search, and more later) without letting any provider's
quirks leak into business logic, and without a missing API key taking the whole
system down.

## Decision

**Evidence records are the spine.** Collectors never hand data directly to
analysis. Every provider emits `Evidence` (`collectors/base.py`) — a Pydantic
model carrying:

- the verbatim provider payload (`raw`), retained for audit;
- normalized `title` / `content`;
- `source_url`, `collector`, `collected_at`, and optional `published_at`;
- a `reliability` prior in `[0, 1]` (the source's inherent trustworthiness);
- an optional `confidence` in `[0, 1]`, left `None` at collection time and
  filled in later by processing.

Because every datum is self-describing, any downstream conclusion can be linked
back to the exact record — and the record back to the original bytes.

**Reliability is a per-source prior, set at the adapter.** SEC EDGAR is `0.98`
(regulatory, keyless, authoritative); Firecrawl website content is `0.9`
(first-party — authoritative about itself but promotional in tone); SerpAPI
web/news results are `0.65` (third-party, corroboration lifts per-item
confidence downstream). Reliability is the source's *prior*; confidence is what
processing computes *per item* from that prior plus recency and corroboration.

**One adapter contract, one registry entry per provider.** `BaseCollector` is an
ABC with `name`, `categories` (which `DataCategory` values it serves), a
`reliability` prior, and an `async collect(target) -> CollectorResult`. Adding a
provider means adding one subclass plus one `@register(...)` factory; business
logic never names a concrete provider. `CollectorResult` bundles the evidence
list with per-run `warnings` and timing, so a provider can return *partial*
results (e.g. "no website known; skipped") without raising.

**Credential-driven auto-enablement.** The registry
(`collectors/registry.py`) maps provider name → factory. A factory returns a
collector, or `None` when its required credentials are absent in `Settings`.
`build_enabled()` instantiates every registered collector whose requirements are
met (with an optional `only` subset for per-request selection). SEC EDGAR needs
no key, so it is always on; Firecrawl and SerpAPI enable themselves only when
their key is present. A missing key silently drops one source rather than
failing the run.

**Typed, provider-agnostic errors.** Failures surface as `CollectorError`
subtypes — `AuthError`, `RateLimitedError`, `ProviderUnavailableError` — each
tagged with the collector name. Callers branch on failure *class*, not on a
provider's specific HTTP status semantics.

**Retry returns the final response; collectors own interpretation.**
`with_retries` (`collectors/resilience.py`) retries transport errors and a fixed
set of retryable status codes (`429, 500, 502, 503, 504`) with jittered
exponential backoff. Crucially, once attempts are exhausted it *returns* the last
response rather than raising, so each collector maps a persistent status to the
right typed error itself (a lingering `429` → `RateLimitedError`, `401/403` →
`AuthError`). It raises only when every attempt failed at the transport layer.
Rate limiting and circuit breaking are expected to move to Redis-backed
implementations when the job queue lands; the call-site API is designed to stay
stable across that change.

## Consequences

- **Auditability by construction.** Every fact keeps its raw payload and source
  URL, so reports can cite sources and claims can be re-verified. This is the
  foundation the later analysis layer builds `Basis` (sourced / inferred /
  assumption) and `Confidence` on (`core/types.py`).
- **Graceful degradation.** The system runs on whatever credentials exist — even
  just the keyless SEC collector — instead of demanding a full key set. Partial
  results are a first-class outcome, matching the `PARTIAL` job stage.
- **Cheap provider onboarding.** New sources are one subclass + one registry
  entry; no orchestration or analysis code changes.
- **Reliability data is retained but not yet consumed at collection time.** The
  prior is stored on every record; turning it (plus recency and corroboration)
  into per-item confidence is deferred to the processing layer
  (see [ADR 0002](0002-data-processing-pipeline.md)).
- **`raw` payloads cost storage.** Keeping verbatim provider responses inflates
  record size; accepted deliberately as the price of auditability. Firecrawl
  content is already capped (`MAX_CONTENT_CHARS = 40_000`) to bound the worst
  case.
- **Retry semantics put responsibility on collectors.** Because `with_retries`
  returns rather than raises on a persistent bad status, every collector must
  check status codes explicitly. This is intentional (providers disagree on what
  a `403` means) but is a contract each new adapter has to honor.

## References

- `collectors/base.py` — `Evidence`, `CompanyTarget`, `CollectorResult`,
  `BaseCollector`, error hierarchy
- `collectors/registry.py` — `register`, `build_enabled`
- `collectors/resilience.py` — `with_retries`
- `collectors/sec_edgar.py`, `collectors/firecrawl.py`, `collectors/serpapi.py`
- `core/config.py` — `Settings` (credential-driven enablement)
- `core/types.py` — `DataCategory`, `JobStage`, `Basis`, `Confidence`
