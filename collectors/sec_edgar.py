"""SEC EDGAR collector — free, keyless, highest-reliability source for public companies.

Flow: resolve company name/ticker to a CIK via the company_tickers.json index,
then pull recent filings from the submissions API. SEC requires a descriptive
User-Agent header on every request.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from collectors.base import (
    BaseCollector,
    CollectorResult,
    CompanyTarget,
    Evidence,
    ProviderUnavailableError,
)
from collectors.registry import register
from collectors.resilience import with_retries
from core.config import Settings
from core.types import DataCategory

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
FILING_INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}-index.htm"

RELEVANT_FORMS = {"10-K", "10-Q", "8-K", "S-1", "S-1/A", "20-F", "DEF 14A", "424B4"}
MAX_FILINGS = 20


class SecEdgarCollector(BaseCollector):
    name = "sec_edgar"
    categories = frozenset({DataCategory.FILINGS, DataCategory.FINANCIALS})
    reliability = 0.98

    def __init__(self, client: httpx.AsyncClient, user_agent: str) -> None:
        super().__init__(client)
        self._headers = {"User-Agent": user_agent}

    async def collect(self, target: CompanyTarget) -> CollectorResult:
        cik = await self._resolve_cik(target)
        if cik is None:
            return self._result(
                [], warnings=[f"No SEC registrant matched {target.name!r}; likely private."]
            )
        submissions = await self._get_json(SUBMISSIONS_URL.format(cik=cik))
        return self._result(self._filings_to_evidence(target, cik, submissions))

    async def _resolve_cik(self, target: CompanyTarget) -> int | None:
        data = await self._get_json(TICKERS_URL)
        entries = list(data.values())
        # An explicit ticker is unambiguous — give it a full pass before name matching.
        if target.ticker:
            ticker = target.ticker.upper()
            for entry in entries:
                if str(entry.get("ticker", "")).upper() == ticker:
                    return int(entry["cik_str"])
        wanted_names = {target.name.lower(), *(a.lower() for a in target.aliases)}
        for entry in entries:
            title = str(entry.get("title", "")).lower()
            if any(name and name in title for name in wanted_names):
                return int(entry["cik_str"])
        return None

    async def _get_json(self, url: str) -> Any:
        response = await with_retries(lambda: self._client.get(url, headers=self._headers))
        if response.status_code != 200:
            raise ProviderUnavailableError(self.name, f"{url} returned {response.status_code}")
        return response.json()

    def _filings_to_evidence(
        self, target: CompanyTarget, cik: int, submissions: dict[str, Any]
    ) -> list[Evidence]:
        recent = submissions.get("filings", {}).get("recent", {})
        forms: list[str] = recent.get("form", [])
        dates: list[str] = recent.get("filingDate", [])
        accessions: list[str] = recent.get("accessionNumber", [])
        docs: list[str] = recent.get("primaryDocDescription", [])

        evidence: list[Evidence] = []
        for i, form in enumerate(forms):
            if form not in RELEVANT_FORMS or len(evidence) >= MAX_FILINGS:
                continue
            accession = accessions[i].replace("-", "")
            filed = dates[i]
            description = docs[i] if i < len(docs) and docs[i] else form
            evidence.append(
                Evidence(
                    company=target.name,
                    category=DataCategory.FILINGS,
                    title=f"{form} filed {filed}",
                    content=(
                        f"{submissions.get('name', target.name)} filed a {form} on {filed}: "
                        f"{description}"
                    ),
                    raw={"form": form, "filingDate": filed, "accessionNumber": accessions[i]},
                    source_url=FILING_INDEX_URL.format(cik=cik, accession=accession),
                    collector=self.name,
                    published_at=datetime.strptime(filed, "%Y-%m-%d").replace(tzinfo=UTC),
                    reliability=self.reliability,
                )
            )
        return evidence


@register("sec_edgar")
def _factory(client: httpx.AsyncClient, settings: Settings) -> BaseCollector | None:
    return SecEdgarCollector(client, settings.sec_edgar_user_agent)
