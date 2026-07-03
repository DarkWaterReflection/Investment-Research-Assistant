"""SerpAPI collector — web search and news verticals for the target company.

One adapter covers several data needs (news, general presence, public
LinkedIn/Glassdoor snippets) because SerpAPI exposes search verticals behind
a single API. Only public search-result snippets are collected.
"""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

import httpx

from collectors.base import (
    AuthError,
    BaseCollector,
    CollectorResult,
    CompanyTarget,
    Evidence,
    ProviderUnavailableError,
    RateLimitedError,
)
from collectors.registry import register
from collectors.resilience import with_retries
from core.config import Settings
from core.types import DataCategory

SEARCH_URL = "https://serpapi.com/search"
MAX_RESULTS_PER_VERTICAL = 10


class SerpApiCollector(BaseCollector):
    name = "serpapi"
    categories = frozenset({DataCategory.NEWS, DataCategory.SOCIAL, DataCategory.REVIEWS})
    reliability = 0.65  # third-party web results; corroboration raises per-item confidence later

    def __init__(self, client: httpx.AsyncClient, api_key: str) -> None:
        super().__init__(client)
        self._api_key = api_key

    async def collect(self, target: CompanyTarget) -> CollectorResult:
        warnings: list[str] = []
        evidence: list[Evidence] = []

        organic = await self._search({"engine": "google", "q": f'"{target.name}" company'})
        evidence += self._organic_to_evidence(target, organic)

        news = await self._search(
            {"engine": "google_news", "q": target.name, "gl": "us", "hl": "en"}
        )
        news_items = self._news_to_evidence(target, news)
        if not news_items:
            warnings.append(f"No recent news found for {target.name!r}.")
        evidence += news_items

        return self._result(evidence, warnings=warnings)

    async def _search(self, params: dict[str, str]) -> dict[str, Any]:
        response = await with_retries(
            lambda: self._client.get(SEARCH_URL, params={**params, "api_key": self._api_key})
        )
        if response.status_code in (401, 403):
            raise AuthError(self.name, "API key rejected")
        if response.status_code == 429:
            raise RateLimitedError(self.name, "rate limited")
        if response.status_code != 200:
            raise ProviderUnavailableError(self.name, f"search returned {response.status_code}")
        result: dict[str, Any] = response.json()
        return result

    def _organic_to_evidence(
        self, target: CompanyTarget, payload: dict[str, Any]
    ) -> list[Evidence]:
        evidence: list[Evidence] = []
        for item in payload.get("organic_results", [])[:MAX_RESULTS_PER_VERTICAL]:
            link = item.get("link")
            snippet = item.get("snippet", "")
            if not link or not snippet:
                continue
            evidence.append(
                Evidence(
                    company=target.name,
                    category=DataCategory.SOCIAL,
                    title=item.get("title", link),
                    content=snippet,
                    raw=item,
                    source_url=link,
                    collector=self.name,
                    reliability=self.reliability,
                )
            )
        return evidence

    def _news_to_evidence(self, target: CompanyTarget, payload: dict[str, Any]) -> list[Evidence]:
        evidence: list[Evidence] = []
        for item in payload.get("news_results", [])[:MAX_RESULTS_PER_VERTICAL]:
            link = item.get("link")
            if not link:
                continue
            published_at: datetime | None = None
            with suppress(ValueError, TypeError):
                published_at = datetime.fromisoformat(str(item.get("date", ""))[:19]).replace(
                    tzinfo=UTC
                )
            evidence.append(
                Evidence(
                    company=target.name,
                    category=DataCategory.NEWS,
                    title=item.get("title", link),
                    content=item.get("snippet") or item.get("title", ""),
                    raw=item,
                    source_url=link,
                    collector=self.name,
                    published_at=published_at,
                    reliability=self.reliability,
                )
            )
        return evidence


@register("serpapi")
def _factory(client: httpx.AsyncClient, settings: Settings) -> BaseCollector | None:
    if settings.serpapi_api_key is None:
        return None
    return SerpApiCollector(client, settings.serpapi_api_key.get_secret_value())
