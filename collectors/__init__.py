"""Data-provider adapters. Importing this package populates the registry."""

from collectors import firecrawl, sec_edgar, serpapi  # noqa: F401  (registry side effects)
from collectors.base import (
    BaseCollector,
    CollectorError,
    CollectorResult,
    CompanyTarget,
    Evidence,
)
from collectors.registry import build_enabled, registered_names

__all__ = [
    "BaseCollector",
    "CollectorError",
    "CollectorResult",
    "CompanyTarget",
    "Evidence",
    "build_enabled",
    "registered_names",
]
