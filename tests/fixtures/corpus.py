"""A realistic Evidence corpus for exercising the processors end-to-end.

``build_corpus`` returns ~15 Evidence records about a fictional target,
"Acme Robotics", deliberately seeded with the messy situations the pipeline
must survive: exact-URL duplicates that differ only by tracking parameters,
near-duplicate news wire copy carried by two outlets, two funding items that
disagree on the Series B amount, an item about an unrelated "Acme", records
with and without ``published_at``, and HTML-polluted text.

Records carry stable ``ev*`` ids so tests can assert on specific merges and
quarantines rather than fishing by content.
"""

from __future__ import annotations

from datetime import UTC, datetime

from collectors.base import CompanyTarget, Evidence
from core.types import DataCategory


def _dt(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


def build_target() -> CompanyTarget:
    """The research subject the fixture corpus is about."""
    return CompanyTarget(
        name="Acme Robotics",
        website="https://acme-robotics.example",
        aliases=["Acme Robotics Inc", "AcmeBot"],
        ticker="ACME",
    )


def build_corpus() -> list[Evidence]:
    """Return the seeded Evidence corpus (order is intentionally shuffled)."""
    return [
        # -- Website (domain match; HTML-polluted content). --
        Evidence(
            id="ev01",
            company="Acme Robotics",
            category=DataCategory.WEBSITE,
            title="<h1>About Acme Robotics</h1>",
            content="<p>Acme&nbsp;Robotics builds <b>warehouse automation</b> robots.</p>",
            source_url="https://acme-robotics.example/about",
            collector="firecrawl",
            reliability=0.9,
        ),
        # -- Funding: Series B at $40M, with tracking params on the URL. --
        Evidence(
            id="ev02",
            company="Acme Robotics",
            category=DataCategory.FUNDING,
            title="Acme Robotics closes Series B",
            content=(
                "Acme Robotics has raised a $40M Series B round led by Foo Ventures "
                "on 2024-03-15."
            ),
            source_url="https://techcrunch.example/acme-series-b?utm_source=twitter&utm_medium=social",
            collector="serpapi",
            reliability=0.7,
            published_at=_dt(2024, 3, 15),
        ),
        # -- Exact-URL duplicate of ev02: same canonical URL, only utm differs. --
        Evidence(
            id="ev03",
            company="Acme Robotics",
            category=DataCategory.FUNDING,
            title="Acme Robotics closes Series B",
            content=(
                "Acme Robotics has raised a $40M Series B round led by Foo Ventures "
                "on 2024-03-15."
            ),
            source_url="https://techcrunch.example/acme-series-b?utm_source=newsletter&utm_campaign=daily",
            collector="serpapi",
            reliability=0.6,
            published_at=_dt(2024, 3, 15),
        ),
        # -- News wire copy, outlet one. --
        Evidence(
            id="ev04",
            company="Acme Robotics",
            category=DataCategory.NEWS,
            title="Acme Robotics expands manufacturing",
            content=(
                "Acme Robotics announced today that it has closed a Series B financing "
                "round to expand its manufacturing operations across North America."
            ),
            source_url="https://outlet-one.example/acme",
            collector="serpapi",
            reliability=0.65,
            published_at=_dt(2024, 3, 16),
        ),
        # -- Near-duplicate of ev04 (one extra token), outlet two, different URL. --
        Evidence(
            id="ev05",
            company="Acme Robotics",
            category=DataCategory.NEWS,
            title="Acme Robotics expands manufacturing footprint",
            content=(
                "Acme Robotics announced today that it has closed a Series B financing "
                "round to expand its manufacturing operations across North America region."
            ),
            source_url="https://outlet-two.example/acme-news",
            collector="serpapi",
            reliability=0.55,
            published_at=_dt(2024, 3, 16),
        ),
        # -- Funding: conflicting Series B amount ($52M vs ev02's $40M). --
        Evidence(
            id="ev06",
            company="Acme Robotics",
            category=DataCategory.FUNDING,
            title="Inside Acme Robotics' Series B",
            content=(
                "In its Series B, Acme Robotics secured $52M from investors, "
                "according to people familiar with the deal."
            ),
            source_url="https://business-news.example/acme-funding",
            collector="serpapi",
            reliability=0.6,
            published_at=_dt(2024, 3, 20),
        ),
        # -- Off-target: a different Acme entirely. Must be quarantined. --
        Evidence(
            id="ev07",
            company="Acme Bakery",
            category=DataCategory.NEWS,
            title="Acme Bakery opens downtown",
            content="Acme Bakery opens a new storefront downtown, selling fresh sourdough.",
            source_url="https://localnews.example/acme-bakery",
            collector="serpapi",
            reliability=0.5,
            published_at=_dt(2024, 2, 1),
        ),
        # -- Investors; no published_at (timeline must fall back to collected_at). --
        Evidence(
            id="ev08",
            company="Acme Robotics",
            category=DataCategory.INVESTORS,
            title="Acme Robotics investor roster",
            content="Foo Ventures and Bar Capital are lead investors in Acme Robotics.",
            source_url="https://crunchbase.example/acme",
            collector="serpapi",
            reliability=0.75,
        ),
        # -- Founders (domain match). --
        Evidence(
            id="ev09",
            company="Acme Robotics",
            category=DataCategory.FOUNDERS,
            title="The team behind Acme Robotics",
            content="Acme Robotics was founded by Jane Smith and John Doe in 2019.",
            source_url="https://acme-robotics.example/team",
            collector="firecrawl",
            reliability=0.9,
            published_at=_dt(2019, 6, 1),
        ),
        # -- Competitors. --
        Evidence(
            id="ev10",
            company="Acme Robotics",
            category=DataCategory.COMPETITORS,
            title="Warehouse robotics landscape",
            content="Acme Robotics competes with Globex Automation and Initech Systems.",
            source_url="https://industry.example/report",
            collector="serpapi",
            reliability=0.6,
            published_at=_dt(2024, 1, 10),
        ),
        # -- Hiring; HTML-polluted; no published_at. --
        Evidence(
            id="ev11",
            company="Acme Robotics",
            category=DataCategory.HIRING,
            title="<span>Careers at Acme Robotics</span>",
            content="<div>Acme Robotics is hiring 50 engineers this quarter.</div>",
            source_url="https://jobs.example/acme",
            collector="firecrawl",
            reliability=0.55,
        ),
        # -- Filings (high reliability, SEC-style). --
        Evidence(
            id="ev12",
            company="Acme Robotics",
            category=DataCategory.FILINGS,
            title="Acme Robotics Inc annual report",
            content="Acme Robotics Inc reported revenue of USD 1.2 billion in fiscal 2023.",
            source_url="https://sec.example/acme-10k",
            collector="sec_edgar",
            reliability=0.95,
            published_at=_dt(2024, 4, 1),
        ),
        # -- Technology (subdomain of the target's site -> domain match). --
        Evidence(
            id="ev13",
            company="Acme Robotics",
            category=DataCategory.TECHNOLOGY,
            title="How Acme Robotics builds its stack",
            content="Acme Robotics uses computer vision and reinforcement learning.",
            source_url="https://blog.acme-robotics.example/tech",
            collector="firecrawl",
            reliability=0.7,
            published_at=_dt(2024, 5, 1),
        ),
        # -- Reviews; no published_at. --
        Evidence(
            id="ev14",
            company="Acme Robotics",
            category=DataCategory.REVIEWS,
            title="Acme Robotics customer sentiment",
            content="Customers rate Acme Robotics highly for reliability and support.",
            source_url="https://reviews.example/acme",
            collector="serpapi",
            reliability=0.4,
        ),
        # -- Market sizing that still names the target. --
        Evidence(
            id="ev15",
            company="Acme Robotics",
            category=DataCategory.MARKET,
            title="Warehouse robotics market outlook",
            content=(
                "The warehouse robotics market, where Acme Robotics operates, is "
                "projected to reach $8 billion by 2027."
            ),
            source_url="https://market-research.example/robotics",
            collector="serpapi",
            reliability=0.5,
            published_at=_dt(2024, 6, 1),
        ),
    ]
