# 2. Data-processing and validation pipeline

- Status: Accepted
- Date: 2026-07-04
- Phase: 2

## Context

The collection layer ([ADR 0001](0001-evidence-first-architecture.md)) produces
raw `Evidence` from several providers. That evidence is noisy in ways that would
poison analysis if passed through unfiltered:

- content carries HTML markup, entity escapes, and control characters;
- the same story appears from multiple sources and via tracking-decorated URLs,
  inflating apparent corroboration;
- search results sometimes describe a *different* company that shares a name —
  in automated due diligence, silently mixing in the wrong company's facts is
  the single most damaging failure, because the output still looks plausible;
- every record still carries only a source *prior*, not a per-item confidence;
- sources genuinely disagree (e.g. two funding figures for the same round), and
  an automated "pick one" can launder a guess into an apparent fact.

The processing layer sits between collection and analysis and must resolve this
while preserving the auditability guarantee: transforms must never destroy the
original evidence.

## Decision

A `ValidationPipeline.run(evidence, target)` runs the corpus through ordered
stages — clean → dedupe → entity-resolve → confidence → conflicts → timeline —
and emits a `ProcessedCorpus` with six fields: `evidence` (the vetted, scored,
on-target items), `quarantined` (off-target items set aside), `merged` (dropped →
kept id pairs from dedupe, so no provenance is lost), `conflicts`, `timeline`, and
`warnings`. Each stage is an independent, testable module under `processors/`
(the private `_text.py` helper provides the shared `tokenize`/`jaccard`/
`content_similarity` used by dedupe and confidence corroboration). The pipeline
raises a warning when more than **30%** of resolved evidence is quarantined
(target resolution may be too narrow) and when any conflicts are found — it
surfaces judgment calls rather than making them silently. The key decisions:

### Immutable transforms

No stage mutates an input `Evidence`. Cleaning returns a fresh copy via
`Evidence.model_copy(update=...)` (`processors/cleaning.py`), stripping HTML and
normalizing whitespace/control chars on `title` and `content` while leaving the
verbatim `raw` payload untouched. The original bytes stay auditable at every
step, honoring ADR 0001.

### Rule-based NER, not spaCy

Entity extraction (money, dates, orgs, people) is **rule-based** —
regex/pattern matching over cleaned text — rather than a statistical model.

- *Why:* a spaCy (or transformer) model means a multi-hundred-MB model download,
  which bloats CI runtime and the deployment container, and adds a heavyweight
  dependency for what is currently a modest extraction need. Rule-based
  extraction is deterministic, fast, dependency-free, and trivially testable.
- *Trade-off:* lower recall and precision on messy free text, and rules need
  hand-maintenance as new patterns appear.
- *Revisit criteria:* move to a model-based NER when extraction accuracy
  measurably blocks report quality — e.g. entity precision/recall on a labeled
  sample falls below an acceptable bar, or the rules become unmaintainable. The
  boundary is deliberately kept behind a module seam so the swap is local.

### Quarantine over deletion for entity mismatches

Entity resolution matches each record against the target's name, aliases, and
domain. Evidence that fails to match is **quarantined, not deleted** — set aside
with a reason rather than dropped. Because evidence about the *wrong* company is
the top silent failure mode, keeping mismatches visible (for review and for
audit) is safer than silently discarding them, and avoids destroying data on a
false-negative match.

### Conflict surfacing over auto-resolution

`detect_conflicts` looks only at `FUNDING`-category evidence. It groups items by
the funding round they name (Pre-Seed, Seed, Series A–F, matched by regex, with
Pre-Seed taking precedence over a bare "seed" match), takes each item's
**headline figure** (the largest money amount it mentions, via the rule-based
NER), and raises a `Conflict` when the smallest and largest headline figures in a
round differ by **more than 10%** (`_AMOUNT_TOLERANCE = 0.10`). The `Conflict`
record carries the field, the disagreeing values, and every contributing
`evidence_id` — it **surfaces both sources with the discrepancy** and never
auto-resolves to one value. Auto-resolution would convert a genuine disagreement
into a false certainty; a human (or the later analysis layer, with its
`Basis`/`Confidence` model) decides. The pipeline also emits a warning noting how
many unresolved conflicts were found.

### Confidence formula and parameters

Per-item confidence is computed from the source prior and two adjustments:

```
confidence = clamp(
    source_prior * recency_decay(age, half_life=365d) * corroboration_boost,
    0.0, 1.0,
)
```

- **`source_prior`** — the collector's `reliability` from ADR 0001 (SEC `0.98`,
  Firecrawl `0.9`, SerpAPI `0.65`).
- **`recency_decay`** — exponential decay with a **365-day half-life**
  (`0.5 ** (age_days / 365)`): a fact loses half its confidence weight per year
  of age. Age is measured from `published_at`. When `published_at` is absent, the
  factor is **1.0 (no decay)** rather than a `collected_at` fallback — undated
  evidence is not penalized on freshness. (Note: this differs from the timeline
  stage, which *does* fall back to `collected_at` for ordering.)
- **`corroboration_boost`** — each *other* evidence item in the **same
  `DataCategory`** whose content Jaccard similarity is **≥ 0.3** counts as a
  supporter, adding **+0.1** to the multiplier, **capped at 1.3**. The cap keeps
  corroboration able to lift but not dominate a weak source, so a flood of
  low-quality echoes cannot manufacture certainty. This corroboration threshold
  (`0.3`) is intentionally much looser than the dedupe threshold (`0.9`): dedupe
  wants near-identical reprints, whereas corroboration rewards merely
  topically-agreeing items.
- The product is **clamped to `[0, 1]`**, matching the `Evidence.confidence`
  field bound. Scoring is applied via `apply_confidence`, which returns fresh
  copies (`model_copy`) with `confidence` set — the input evidence is not
  mutated.

Parameters (half-life 365d, corroboration +0.1/supporter capped at 1.3,
corroboration similarity 0.3) are chosen as defensible starting points, not tuned
constants; they are centralized at the top of `processors/reliability.py` so they
can be adjusted as real corpora are observed.

### Dedupe: canonical URL + content Jaccard

Deduplication works in two passes:

1. **Canonical URL** — strip tracking parameters (utm_*, and similar) so the
   same page under different decorated links collapses to one.
2. **Content similarity** — token-set **Jaccard ≥ 0.9** (`processors/_text.py`)
   treats near-identical content as duplicate.

When duplicates are found, the record with the **highest reliability** is kept,
so a wire story surviving as its most authoritative copy. The 0.9 threshold is
deliberately conservative: it catches reprints without merging two genuinely
different items that happen to share vocabulary.

### Timeline

A chronological view of company events is assembled from evidence timestamps,
using `published_at` and falling back to `collected_at` when publication date is
unknown. (The confidence recency term does *not* use this fallback — it applies
no decay to undated evidence — so timeline ordering and confidence decay treat a
missing `published_at` differently, by design.) The sort is stable: events
sharing a timestamp preserve input order, for reproducible reports.

## Consequences

- **Analysis receives a clean, deduplicated, on-target corpus** with per-item
  confidence already attached, so the downstream LLM/analysis layer reasons over
  trustworthy inputs and can weight by confidence.
- **No data is destroyed.** Cleaning copies, mismatches are quarantined, and
  conflicts are surfaced — the auditability guarantee from ADR 0001 survives the
  whole pipeline.
- **Determinism and cheap CI.** Rule-based NER and pure-Python similarity keep
  the pipeline dependency-light, fast, and reproducible in CI with no model
  downloads.
- **Accuracy ceiling on extraction.** Rule-based NER will miss entities that a
  trained model would catch; this is an accepted, bounded cost with an explicit
  revisit path.
- **Tuning debt.** The confidence parameters and the Jaccard/conflict thresholds
  are first-guess values; they will need calibration against real corpora, and
  are centralized to make that cheap.
- **Human/downstream burden for conflicts and quarantine.** By refusing to
  auto-resolve, the pipeline pushes genuinely ambiguous cases to later stages or
  to a human — the correct trade for a due-diligence tool, at the cost of not
  fully "deciding" on its own.

## References

- `processors/pipeline.py` — `ValidationPipeline`, `ProcessedCorpus`
- `processors/cleaning.py` — `clean_evidence`/`clean_text` (immutable via `model_copy`)
- `processors/dedupe.py` — `dedupe_evidence`, `canonicalize_url`, `DedupeResult`
- `processors/entity_resolution.py` — `resolve_entities`, `EntityResolutionResult`
- `processors/reliability.py` — `score_confidence`, `apply_confidence`
  (half-life, corroboration constants)
- `processors/conflicts.py` — `detect_conflicts`, `Conflict`
- `processors/ner.py` — `extract_entities`, `ExtractedEntities`, `MoneyMention`
- `processors/timeline.py` — `build_timeline`, `TimelineEvent`
- `processors/_text.py` — `tokenize`, `jaccard`, `content_similarity`
- [ADR 0001](0001-evidence-first-architecture.md) — `Evidence`, reliability
  priors, `DataCategory`
- `core/types.py` — `Basis`, `Confidence`, `JobStage` (`VALIDATING`)
