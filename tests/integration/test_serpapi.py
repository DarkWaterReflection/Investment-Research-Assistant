import pytest
import respx

from collectors.base import RateLimitedError
from collectors.serpapi import SEARCH_URL, SerpApiCollector
from core.types import DataCategory

ORGANIC_FIXTURE = {
    "organic_results": [
        {
            "title": "Acme Robotics | LinkedIn",
            "link": "https://www.linkedin.com/company/acme-robotics",
            "snippet": "Acme Robotics | 5,000 followers. Warehouse automation.",
        },
        {"title": "No snippet entry", "link": "https://example.com/skip-me"},
    ]
}

NEWS_FIXTURE = {
    "news_results": [
        {
            "title": "Acme Robotics raises $40M",
            "link": "https://techdaily.example/acme-40m",
            "snippet": "Series B led by Example Ventures.",
            "date": "2026-06-30T09:00:00",
        }
    ]
}


@pytest.fixture
def collector(http_client) -> SerpApiCollector:
    return SerpApiCollector(http_client, "serp-test-key")


@respx.mock
async def test_collects_organic_and_news_evidence(collector, target):
    respx.get(SEARCH_URL, params__contains={"engine": "google"}).respond(json=ORGANIC_FIXTURE)
    respx.get(SEARCH_URL, params__contains={"engine": "google_news"}).respond(json=NEWS_FIXTURE)

    result = await collector.collect(target)

    by_category = {ev.category for ev in result.evidence}
    assert by_category == {DataCategory.SOCIAL, DataCategory.NEWS}
    assert len(result.evidence) == 2  # snippetless organic result dropped

    news = next(ev for ev in result.evidence if ev.category == DataCategory.NEWS)
    assert news.published_at is not None
    assert news.published_at.year == 2026
    assert result.warnings == []


@respx.mock
async def test_no_news_produces_warning(collector, target):
    respx.get(SEARCH_URL, params__contains={"engine": "google"}).respond(json=ORGANIC_FIXTURE)
    respx.get(SEARCH_URL, params__contains={"engine": "google_news"}).respond(json={})

    result = await collector.collect(target)

    assert any("news" in w.lower() for w in result.warnings)


@respx.mock
async def test_persistent_rate_limit_raises_typed_error(collector, target):
    respx.get(SEARCH_URL).respond(status_code=429)

    with pytest.raises(RateLimitedError):
        await collector.collect(target)
