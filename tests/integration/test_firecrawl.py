import pytest
import respx

from collectors.base import AuthError, CompanyTarget
from collectors.firecrawl import SCRAPE_URL, FirecrawlCollector
from core.types import DataCategory

SCRAPE_FIXTURE = {
    "success": True,
    "data": {
        "markdown": "# Acme Robotics\nWe build warehouse automation robots.",
        "metadata": {"title": "Acme Robotics — Warehouse Automation"},
    },
}


@pytest.fixture
def collector(http_client) -> FirecrawlCollector:
    return FirecrawlCollector(http_client, "fc-test-key")


@respx.mock
async def test_scrape_yields_website_evidence(collector, target):
    route = respx.post(SCRAPE_URL).respond(json=SCRAPE_FIXTURE)

    result = await collector.collect(target)

    assert route.calls.last.request.headers["Authorization"] == "Bearer fc-test-key"
    (ev,) = result.evidence
    assert ev.category == DataCategory.WEBSITE
    assert ev.title == "Acme Robotics — Warehouse Automation"
    assert "warehouse automation" in ev.content.lower()
    assert ev.source_url == str(target.website)
    assert ev.raw == SCRAPE_FIXTURE  # verbatim payload retained


async def test_target_without_website_is_skipped_with_warning(collector):
    result = await collector.collect(CompanyTarget(name="Stealth Co"))

    assert result.evidence == []
    assert "skipped" in result.warnings[0].lower()


@respx.mock
async def test_rejected_key_raises_auth_error(collector, target):
    respx.post(SCRAPE_URL).respond(status_code=401)

    with pytest.raises(AuthError):
        await collector.collect(target)


@respx.mock
async def test_empty_scrape_returns_warning(collector, target):
    respx.post(SCRAPE_URL).respond(json={"success": True, "data": {"markdown": "  "}})

    result = await collector.collect(target)

    assert result.evidence == []
    assert result.warnings
