# 3. LLM abstraction and citation enforcement

- Status: Accepted
- Date: 2026-07-04
- Phase: 3

## Context

Analysis must reason over the `ProcessedCorpus` (ADR 0002) using a language
model, but three risks follow directly from the project's guiding principle
(an unsourced or mis-attributed fact is worse than a missing one):

- an LLM will confidently **fabricate citations** — evidence IDs that look
  plausible but don't exist;
- structured output drifts: models return malformed JSON or schema-invalid
  objects some fraction of the time;
- the platform must be **provider-configurable** (Anthropic / OpenAI /
  Gemini) without letting any vendor's SDK or output quirks leak into
  business logic.

## Decision

An `llm/` layer with a hard boundary: providers are thin transport adapters
that return raw dicts plus usage accounting; **all validation and citation
enforcement happens in one place** (`llm/validation.py`), identically for
every provider.

### Thin providers over raw HTTP, no vendor SDKs

`BaseLLMProvider.complete_structured(system, prompt, schema, max_tokens)` →
`LLMResult{payload: dict, usage: LLMUsage}`. Each adapter is ~100 lines of
httpx against the vendor's REST API, reusing the collector layer's
`with_retries` backoff:

- **Anthropic** — a single forced tool call (`tool_choice: {"type": "tool"}`)
  whose `input_schema` is the Pydantic model's JSON schema.
- **OpenAI** — forced function calling (same idea, `tool_choice: function`).
- **Gemini** — `responseMimeType: application/json` with the schema embedded
  in the system instruction, because Gemini's typed `responseSchema` dialect
  rejects keywords Pydantic emits (`$defs`, `allOf`).

*Why no SDKs:* three vendor SDKs would triple the dependency surface and each
hides its own retry/timeout policy; raw HTTP keeps behavior uniform and
respx-testable. *Trade-off:* we own request-shape maintenance as APIs evolve.

Errors are typed like collector errors: `LLMAuthError`, `LLMRateLimitedError`,
`LLMUnavailableError`, `MalformedOutputError` — callers never parse vendor
error bodies.

### One repair retry, then a typed failure

`generate_validated(provider, system, prompt, schema, known_evidence_ids)`:

1. Validate the payload against the schema. On failure, make **one** repair
   call (the model sees its previous output and the validation errors), then
   raise `MalformedOutputError`. Unbounded repair loops would hide a broken
   prompt behind rising cost.
2. Enforce citations (below), again with one repair budget.

### Citation enforcement: repair, then downgrade — never trust, never drop

Every analytical claim is a `Finding{claim, basis, evidence_ids, confidence}`
(`Basis`: sourced / inferred / assumption). After schema validation, findings
are checked against the set of **real corpus evidence IDs**:

- a `sourced` finding citing **no** real ID triggers one repair call listing
  the offending claims;
- if repair still fails, the claim is **downgraded to `inferred`** and the
  fabricated IDs stripped, each recorded as a warning — the claim survives,
  but it can no longer masquerade as sourced;
- unknown IDs are always stripped, even from partially-valid citation lists;
- **infrastructure errors always propagate** — only output-quality failures
  take the degrade path, so a rate limit never silently produces a weaker memo.

*Why downgrade instead of delete:* deleting loses analytical signal; keeping
the claim as `sourced` launders a fabrication. Re-labeling with a visible
warning preserves both honesty and content.

### Cost observability with honest unknowns

Every call returns `LLMUsage{tokens, cost_usd, latency}`. Pricing is a
longest-prefix table (`llm/pricing.py`); an unknown model prices as **`None`,
never a guess**, so budget accounting can distinguish "free" from "untracked".

### FakeLLM as a first-class test provider

`llm/fake.py` scripts responses like a tape (payloads or exceptions) and
records every call. The entire adversarial suite — fabricated IDs, malformed
repairs, nested findings, budget behavior — runs with **zero API keys**, in CI
and on developer machines.

## Consequences

- Analysis code is provider-agnostic; switching vendors is one env var
  (`LLM_PROVIDER`/`LLM_MODEL`).
- Fabricated citations cannot reach a report as facts; the failure mode is a
  visibly-labeled inference plus a warning, not silent corruption.
- Worst-case call amplification is bounded at 3× (initial + schema repair +
  citation repair), paid for in the usage record.
- Request shapes are our maintenance burden as vendor APIs evolve; the respx
  tests pin the current contracts.

## References

- `llm/base.py` — `BaseLLMProvider`, `LLMUsage`, typed errors
- `llm/providers/{anthropic,openai,gemini}.py` — transport adapters
- `llm/validation.py` — `generate_validated`, repair prompts, downgrade logic
- `llm/schemas.py` — `Finding`; `core/types.py` — `Basis`, `Confidence`
- `llm/pricing.py` — longest-prefix pricing, `None` for unknown models
- `llm/fake.py` — scripted test provider
