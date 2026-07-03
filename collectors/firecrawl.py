"""Firecrawl collector — company-website content as clean markdown.

Scrapes the target's homepage (and, later, key subpages such as /about and
/careers). Skips gracefully when the target has no known website.
"""

from __future__ import annotations

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

SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"
MAX_CONTENT_CHARS = 40_000


class FirecrawlCollector(BaseCollector):
    name = "firecrawl"
    categories = frozenset({DataCategory.WEBSITE, DataCategory.TECHNOLOGY})
    reliability = 0.9  # first-party content: authoritative about itself, promotional in tone

    def __init__(self, client: httpx.AsyncClient, api_key: str) -> None:
        super().__init__(client)
        self._headers = {"Authorization": f"Bearer {api_key}"}

    async def collect(self, target: CompanyTarget) -> CollectorResult:
        if target.website is None:
            return self._result([], warnings=["No website known for target; skipped."])
        url = str(target.website)
        response = await with_retries(
            lambda: self._client.post(
                SCRAPE_URL,
                headers=self._headers,
                json={"url": url, "formats": ["markdown"]},
            )
        )
        if response.status_code in (401, 403):
            raise AuthError(self.name, "API key rejected")
        if response.status_code == 429:
            raise RateLimitedError(self.name, "rate limited")
        if response.status_code != 200:
            raise ProviderUnavailableError(self.name, f"scrape returned {response.status_code}")

        payload = response.json()
        data = payload.get("data", {})
        markdown: str = data.get("markdown", "")
        if not markdown.strip():
            return self._result([], warnings=[f"Empty content scraped from {url}"])

        metadata = data.get("metadata", {})
        evidence = Evidence(
            company=target.name,
            category=DataCategory.WEBSITE,
            title=metadata.get("title") or f"{target.name} website",
            content=markdown[:MAX_CONTENT_CHARS],
            raw=payload,
            source_url=url,
            collector=self.name,
            reliability=self.reliability,
        )
        return self._result([evidence])


@register("firecrawl")
def _factory(client: httpx.AsyncClient, settings: Settings) -> BaseCollector | None:
    if settings.firecrawl_api_key is None:
        return None
    return FirecrawlCollector(client, settings.firecrawl_api_key.get_secret_value())
