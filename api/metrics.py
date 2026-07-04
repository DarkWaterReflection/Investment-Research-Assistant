"""In-process metrics in Prometheus text exposition format.

Hand-rolled on purpose: a handful of counters needs no client library, stays
fully typed, and keeps the /metrics contract testable as plain text. Values
are process-local; aggregation across replicas is the scraper's job.
"""

from __future__ import annotations

from collections import Counter

from orchestration.jobs import ResearchJobResult


class Metrics:
    """Counters for jobs, tokens, cost and pipeline latency."""

    def __init__(self) -> None:
        self._jobs_by_status: Counter[str] = Counter()
        self._input_tokens = 0
        self._output_tokens = 0
        self._llm_calls = 0
        self._cost_usd = 0.0
        self._duration_sum = 0.0
        self._duration_count = 0

    def record_result(self, result: ResearchJobResult) -> None:
        self._jobs_by_status[str(result.stage)] += 1
        self._cost_usd += result.total_cost_usd
        self._duration_sum += sum(record.duration_seconds for record in result.stages)
        self._duration_count += 1
        if result.analysis is not None:
            for usage in result.analysis.usage:
                self._llm_calls += 1
                self._input_tokens += usage.input_tokens
                self._output_tokens += usage.output_tokens

    def record_error(self) -> None:
        self._jobs_by_status["failed"] += 1

    def render(self) -> str:
        lines = [
            "# HELP ira_jobs_total Research jobs by terminal status.",
            "# TYPE ira_jobs_total counter",
        ]
        lines.extend(
            f'ira_jobs_total{{status="{status}"}} {count}'
            for status, count in sorted(self._jobs_by_status.items())
        )
        lines += [
            "# HELP ira_llm_calls_total LLM calls made across all jobs.",
            "# TYPE ira_llm_calls_total counter",
            f"ira_llm_calls_total {self._llm_calls}",
            "# HELP ira_llm_tokens_total LLM tokens by direction.",
            "# TYPE ira_llm_tokens_total counter",
            f'ira_llm_tokens_total{{direction="input"}} {self._input_tokens}',
            f'ira_llm_tokens_total{{direction="output"}} {self._output_tokens}',
            "# HELP ira_llm_cost_usd_total Estimated LLM spend in USD.",
            "# TYPE ira_llm_cost_usd_total counter",
            f"ira_llm_cost_usd_total {self._cost_usd:.6f}",
            "# HELP ira_job_duration_seconds Total pipeline time per job.",
            "# TYPE ira_job_duration_seconds summary",
            f"ira_job_duration_seconds_sum {self._duration_sum:.6f}",
            f"ira_job_duration_seconds_count {self._duration_count}",
        ]
        return "\n".join(lines) + "\n"
