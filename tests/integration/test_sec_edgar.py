import pytest
import respx

from collectors.base import CompanyTarget, ProviderUnavailableError
from collectors.sec_edgar import SUBMISSIONS_URL, TICKERS_URL, SecEdgarCollector
from core.types import DataCategory

TICKERS_FIXTURE = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 1318605, "ticker": "TSLA", "title": "Tesla, Inc."},
}

SUBMISSIONS_FIXTURE = {
    "name": "Apple Inc.",
    "filings": {
        "recent": {
            "form": ["10-K", "4", "8-K"],
            "filingDate": ["2025-11-01", "2025-10-20", "2025-10-05"],
            "accessionNumber": ["0000320193-25-000001", "x", "0000320193-25-000002"],
            "primaryDocDescription": ["Annual report", "", "Current report"],
        }
    },
}


@pytest.fixture
def collector(http_client) -> SecEdgarCollector:
    return SecEdgarCollector(http_client, "IRA-tests test@example.com")


@respx.mock
async def test_public_company_yields_filing_evidence(collector):
    respx.get(TICKERS_URL).respond(json=TICKERS_FIXTURE)
    respx.get(SUBMISSIONS_URL.format(cik=320193)).respond(json=SUBMISSIONS_FIXTURE)

    result = await collector.collect(CompanyTarget(name="Apple"))

    forms = [ev.raw["form"] for ev in result.evidence]
    assert forms == ["10-K", "8-K"]  # Form 4 (insider trades) filtered out
    ev = result.evidence[0]
    assert ev.category == DataCategory.FILINGS
    assert ev.reliability == 0.98
    assert ev.published_at is not None
    assert "0000320193-25-000001".replace("-", "") in ev.source_url


@respx.mock
async def test_ticker_takes_precedence_over_name(collector):
    respx.get(TICKERS_URL).respond(json=TICKERS_FIXTURE)
    route = respx.get(SUBMISSIONS_URL.format(cik=1318605)).respond(
        json={"name": "Tesla, Inc.", "filings": {"recent": {}}}
    )

    await collector.collect(CompanyTarget(name="Apple", ticker="tsla"))

    assert route.called


@respx.mock
async def test_private_company_returns_warning_not_error(collector):
    respx.get(TICKERS_URL).respond(json=TICKERS_FIXTURE)

    result = await collector.collect(CompanyTarget(name="Acme Robotics"))

    assert result.evidence == []
    assert "private" in result.warnings[0]


@respx.mock
async def test_persistent_5xx_raises_provider_unavailable(collector):
    respx.get(TICKERS_URL).respond(status_code=503)

    with pytest.raises(ProviderUnavailableError):
        await collector.collect(CompanyTarget(name="Apple"))
