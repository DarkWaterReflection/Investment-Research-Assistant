"""The analysis pass roster.

Each pass looks at a slice of the corpus (by evidence category) and answers
one analytical question. Passes are data, not code — adding a memo angle
means adding a PassSpec here, nothing else. The risks pass additionally sees
detected conflicts and quarantine statistics, because disagreement between
sources is itself risk signal.
"""

from __future__ import annotations

from pydantic import BaseModel

from core.types import DataCategory


class PassSpec(BaseModel):
    """One analysis pass: which evidence it reads and what it must answer."""

    name: str
    title: str
    categories: frozenset[DataCategory]
    instructions: str
    include_conflicts: bool = False


PASSES: list[PassSpec] = [
    PassSpec(
        name="company_profile",
        title="Company & Product",
        categories=frozenset(
            {
                DataCategory.WEBSITE,
                DataCategory.TECHNOLOGY,
                DataCategory.SOCIAL,
                DataCategory.PATENTS,
            }
        ),
        instructions=(
            "Describe what the company does: its product or service, the problem it "
            "solves, the technology behind it and any defensibility (patents, "
            "proprietary tech), and how it appears to make money."
        ),
    ),
    PassSpec(
        name="market",
        title="Market & Competition",
        categories=frozenset(
            {
                DataCategory.MARKET,
                DataCategory.INDUSTRY,
                DataCategory.COMPETITORS,
                DataCategory.NEWS,
            }
        ),
        instructions=(
            "Assess the market the company operates in: size and growth signals, "
            "industry dynamics, named competitors and how the company is positioned "
            "against them."
        ),
    ),
    PassSpec(
        name="team",
        title="Team & Organization",
        categories=frozenset(
            {DataCategory.FOUNDERS, DataCategory.LEADERSHIP, DataCategory.HIRING}
        ),
        instructions=(
            "Evaluate the founders and leadership: backgrounds, prior outcomes, "
            "domain fit, and what hiring activity says about the company's "
            "direction and organizational health."
        ),
    ),
    PassSpec(
        name="funding",
        title="Funding & Financials",
        categories=frozenset(
            {
                DataCategory.FUNDING,
                DataCategory.INVESTORS,
                DataCategory.FINANCIALS,
                DataCategory.FILINGS,
            }
        ),
        instructions=(
            "Reconstruct the funding history: rounds, amounts, dates and investors; "
            "note financial disclosures from filings. Where sources disagree on a "
            "figure, present both figures — do not pick a winner."
        ),
    ),
    PassSpec(
        name="traction",
        title="Traction & Customers",
        categories=frozenset(
            {
                DataCategory.CUSTOMERS,
                DataCategory.REVIEWS,
                DataCategory.NEWS,
                DataCategory.SOCIAL,
                DataCategory.HIRING,
            }
        ),
        instructions=(
            "Assess commercial traction: named customers, partnerships, review "
            "sentiment, growth signals in news and hiring. Distinguish announced "
            "intent from demonstrated results."
        ),
    ),
    PassSpec(
        name="risks",
        title="Risks",
        categories=frozenset(DataCategory),
        include_conflicts=True,
        instructions=(
            "Identify the material risks an investor should weigh: market, "
            "execution, financial, regulatory, reputational and key-person risks. "
            "Treat unresolved conflicts between sources and gaps in the evidence "
            "as risk signals in their own right."
        ),
    ),
]

SYNTHESIS_NAME = "synthesis"
