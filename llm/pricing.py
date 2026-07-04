"""Per-model pricing for cost observability.

Prices are USD per million tokens (input, output). Unknown models cost None —
we never fabricate a number, and the budget guard treats None as untracked.
Longest matching prefix wins so dated snapshots (e.g. -20250101) still price.
"""

from __future__ import annotations

PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    # Anthropic
    "claude-fable-5": (25.0, 125.0),
    "claude-opus-4": (15.0, 75.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    # OpenAI
    "gpt-4o-mini": (0.15, 0.6),
    "gpt-4o": (2.5, 10.0),
    "gpt-4.1-mini": (0.4, 1.6),
    "gpt-4.1": (2.0, 8.0),
    # Google
    "gemini-2.5-pro": (1.25, 10.0),
    "gemini-2.5-flash": (0.3, 2.5),
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Estimated call cost, or None when the model has no pricing entry."""
    best: tuple[float, float] | None = None
    best_len = -1
    for prefix, rates in PRICING_PER_MTOK.items():
        if model.startswith(prefix) and len(prefix) > best_len:
            best, best_len = rates, len(prefix)
    if best is None:
        return None
    input_rate, output_rate = best
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000
