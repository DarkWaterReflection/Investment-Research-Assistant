"""Collector contract and the Evidence model — the spine of the platform.

Collectors never hand data directly to analysis. They emit Evidence records
carrying the verbatim payload, normalized content, source URL, timestamps and
a reliability prior, so every downstream conclusion can be audited back to
the original bytes.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, Field, HttpUrl

from core.types import DataCategory


class CompanyTarget(BaseModel):
    """The resolved research subject a collector is asked about."""

    name: str = Field(min_length=1, max_length=200)
    website: HttpUrl | None = None
    aliases: list[str] = Field(default_factory=list)
    ticker: str | None = None


class Evidence(BaseModel):
    """A single sourced datum about the target company."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    company: str
    category: DataCategory
    title: str
    content: str
    raw: Any = None  # verbatim provider payload, retained for audit
    source_url: str
    collector: str
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    published_at: datetime | None = None
    reliability: float = Field(ge=0.0, le=1.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class CollectorResult(BaseModel):
    """Outcome of one collector run: evidence plus diagnostics."""

    collector: str
    evidence: list[Evidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    duration_seconds: float | None = None


class CollectorError(Exception):
    """Base class for typed collector failures."""

    def __init__(self, collector: str, message: str) -> None:
        self.collector = collector
        super().__init__(f"[{collector}] {message}")


class AuthError(CollectorError):
    """Missing or rejected credentials."""


class RateLimitedError(CollectorError):
    """Provider throttled us; retry later."""


class ProviderUnavailableError(CollectorError):
    """Provider down or returning server errors."""


class BaseCollector(ABC):
    """Adapter contract every data provider implements.

    Adding a provider means adding one subclass and a registry entry;
    business logic never names a concrete provider.
    """

    name: str
    categories: frozenset[DataCategory]
    reliability: float  # source prior in [0, 1]

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    @abstractmethod
    async def collect(self, target: CompanyTarget) -> CollectorResult:
        """Gather evidence about the target. Raises CollectorError subtypes."""

    def _result(
        self, evidence: list[Evidence], warnings: list[str] | None = None
    ) -> CollectorResult:
        return CollectorResult(collector=self.name, evidence=evidence, warnings=warnings or [])
