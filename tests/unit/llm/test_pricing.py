import pytest

from llm.pricing import estimate_cost_usd


def test_exact_model_priced():
    # claude-sonnet-5: $3/M input, $15/M output
    assert estimate_cost_usd("claude-sonnet-5", 1_000_000, 1_000_000) == pytest.approx(18.0)


def test_dated_snapshot_matches_by_prefix():
    cost = estimate_cost_usd("claude-sonnet-5-20260101", 1_000_000, 0)
    assert cost == pytest.approx(3.0)


def test_longest_prefix_wins():
    # gpt-4o-mini must not be priced as gpt-4o
    assert estimate_cost_usd("gpt-4o-mini", 1_000_000, 0) == pytest.approx(0.15)
    assert estimate_cost_usd("gpt-4o", 1_000_000, 0) == pytest.approx(2.5)


def test_unknown_model_returns_none_not_a_guess():
    assert estimate_cost_usd("some-local-model", 1_000_000, 1_000_000) is None


def test_zero_tokens_cost_zero():
    assert estimate_cost_usd("gpt-4o", 0, 0) == 0.0
