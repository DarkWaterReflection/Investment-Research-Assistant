"""The analysis engine: a ProcessedCorpus in, an AnalysisResult out.

Passes run sequentially so the cost budget is enforced deterministically:
before each LLM call the engine checks accumulated spend against
Settings.max_cost_per_job_usd and skips the remaining passes once exhausted —
a partial memo with an honest gap beats a complete one that blew the budget.
Passes with no evidence are skipped without spending a call.
"""

from __future__ import annotations

from analysis.passes import PASSES, SYNTHESIS_NAME
from analysis.prompts import (
    SYSTEM_PROMPT,
    build_pass_prompt,
    build_synthesis_prompt,
    select_evidence,
)
from analysis.schemas import AnalysisResult, MemoSynthesis, SectionAnalysis, SectionResult
from collectors.base import CompanyTarget
from core.config import Settings
from llm.base import BaseLLMProvider, LLMUsage
from llm.validation import generate_validated
from processors.pipeline import ProcessedCorpus


class AnalysisEngine:
    """Runs the pass roster over a corpus with cost-budget enforcement."""

    def __init__(self, provider: BaseLLMProvider, settings: Settings) -> None:
        self._provider = provider
        self._budget_usd = settings.max_cost_per_job_usd

    async def run(self, target: CompanyTarget, corpus: ProcessedCorpus) -> AnalysisResult:
        result = AnalysisResult()
        known_ids = {item.id for item in corpus.evidence}

        for spec in PASSES:
            items = select_evidence(corpus.evidence, spec.categories)
            if not items:
                result.skipped_passes.append(spec.name)
                result.warnings.append(f"Skipped pass {spec.name!r}: no evidence in scope.")
                continue
            if self._exhausted(result):
                self._skip_for_budget(result, spec.name)
                continue

            prompt = build_pass_prompt(
                target.name,
                spec,
                items,
                conflicts=corpus.conflicts if spec.include_conflicts else None,
                quarantined_count=len(corpus.quarantined),
            )
            validated = await generate_validated(
                self._provider,
                system=SYSTEM_PROMPT,
                prompt=prompt,
                schema=SectionAnalysis,
                known_evidence_ids=known_ids,
            )
            self._account(result, validated.usage)
            result.sections.append(
                SectionResult(
                    name=spec.name,
                    title=spec.title,
                    analysis=validated.output,
                    evidence_used=[item.id for item in items],
                    warnings=validated.warnings,
                )
            )

        await self._synthesize(target, result, known_ids)
        return result

    async def _synthesize(
        self, target: CompanyTarget, result: AnalysisResult, known_ids: set[str]
    ) -> None:
        if not result.sections:
            result.skipped_passes.append(SYNTHESIS_NAME)
            result.warnings.append("Skipped synthesis: no sections were produced.")
            return
        if self._exhausted(result):
            self._skip_for_budget(result, SYNTHESIS_NAME)
            return
        validated = await generate_validated(
            self._provider,
            system=SYSTEM_PROMPT,
            prompt=build_synthesis_prompt(target.name, result.sections),
            schema=MemoSynthesis,
            known_evidence_ids=known_ids,
        )
        self._account(result, validated.usage)
        result.synthesis = validated.output
        result.warnings.extend(validated.warnings)

    def _exhausted(self, result: AnalysisResult) -> bool:
        return result.total_cost_usd >= self._budget_usd

    def _skip_for_budget(self, result: AnalysisResult, name: str) -> None:
        result.skipped_passes.append(name)
        result.budget_exhausted = True
        result.warnings.append(
            f"Skipped pass {name!r}: cost budget exhausted "
            f"(${result.total_cost_usd:.2f} of ${self._budget_usd:.2f})."
        )

    @staticmethod
    def _account(result: AnalysisResult, usage: list[LLMUsage]) -> None:
        result.usage.extend(usage)
        result.total_cost_usd += sum(u.cost_usd or 0.0 for u in usage)
