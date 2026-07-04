# 4. Analysis passes, budget enforcement, and job orchestration

- Status: Accepted
- Date: 2026-07-05
- Phases: 4–5

## Context

With validated evidence (ADR 0002) and a citation-enforcing LLM layer
(ADR 0003), the system needs to produce the actual memo: multiple analytical
angles over one corpus, a synthesis, and a rendered report — under a hard
cost ceiling, and degrading honestly when sources fail or money runs out.

## Decision

### Passes are data, not code

`analysis/passes.py` declares a roster of `PassSpec{name, title, categories,
instructions}`: company profile, market, team, funding, traction, risks. Each
pass reads only its category slice of the corpus; adding a memo angle means
adding a spec, not code. Two passes are special by declaration, not by code
path: **risks** reads all categories and additionally sees the pipeline's
unresolved `Conflict`s and the quarantine count (source disagreement *is*
risk signal), and **funding** is instructed to present disagreeing figures
side by side, never to pick a winner — extending ADR 0002's
no-auto-resolution rule through the LLM stage.

### Prompt discipline: capped, ranked, citable

Evidence enters prompts as `[id]`-tagged blocks with collector, confidence
and date visible — top **25** items per pass ranked by confidence (falling
back to the reliability prior), content capped at **700 chars** per item. A
large corpus can therefore never blow the context window or the budget; the
cost per pass is bounded by construction.

### Sequential passes with a deterministic budget guard

Passes run **sequentially**, and accumulated spend is checked against
`Settings.max_cost_per_job_usd` *before* each call. Once exhausted, remaining
passes are skipped and recorded (`skipped_passes`, `budget_exhausted`, plus a
warning naming the spend). Parallel passes would be faster but make budget
enforcement racy — a partial memo with an honest gap beats a complete one
that overran its ceiling. Passes with no evidence skip without spending.

### Synthesis reads sections, not raw evidence

The final pass (executive summary, thesis, strengths/concerns, open
questions) consumes the completed section outputs. This keeps the synthesis
prompt small, and its findings must reuse evidence IDs already cited by
sections — the citation enforcer applies unchanged.

### The job orchestrator degrades, it doesn't die

`run_research_job` walks COLLECTING → VALIDATING → ANALYZING → GENERATING
with per-stage timing records. Collectors run concurrently, each fenced by
its own timeout; a failing or hanging collector becomes a **warning** and the
job ends **PARTIAL**. The job ends **FAILED** only when there is nothing to
analyze: no collectors enabled, no evidence collected, or everything
quarantined as off-target. Report generation renders the canonical Markdown
memo (ADR 0002's data-quality information — merges, quarantines, conflicts —
appears *in* the memo, with numbered source footnotes assigned in reading
order). PARTIAL jobs still get a memo; their gaps are visible in Diagnostics.

## Consequences

- Cost per job is bounded and observable; the failure mode of a tight budget
  is a smaller memo that says so, not an overrun or a crash.
- One flaky provider (data or LLM rate limit) degrades output instead of
  failing the job; only genuinely empty corpora fail.
- Sequential passes cost latency (≈7 LLM calls end to end); acceptable for a
  due-diligence workload, revisit if interactive latency ever matters.
- The pass roster is the single tuning surface for memo scope; report
  templates never touch pipeline objects (they render a `ReportContext`
  view-model), so memo layout changes are isolated from analysis changes.

## References

- `analysis/passes.py` — `PassSpec`, roster; `analysis/prompts.py` — caps,
  ranking, `[id]` rendering; `analysis/engine.py` — budget guard
- `orchestration/jobs.py` — `run_research_job`, stage records, PARTIAL/FAILED
- `reports/context.py` — footnote numbering, source register;
  `reports/templates/` — Markdown/HTML memo; `reports/pdf.py` — optional PDF
