"""Shared domain types used across collectors, processors, analysis, and reports."""

from __future__ import annotations

from enum import StrEnum


class DataCategory(StrEnum):
    """What kind of company information a piece of evidence describes."""

    WEBSITE = "website"
    NEWS = "news"
    FUNDING = "funding"
    INVESTORS = "investors"
    COMPETITORS = "competitors"
    INDUSTRY = "industry"
    MARKET = "market"
    FOUNDERS = "founders"
    LEADERSHIP = "leadership"
    CUSTOMERS = "customers"
    HIRING = "hiring"
    REVIEWS = "reviews"
    TECHNOLOGY = "technology"
    SOCIAL = "social"
    PATENTS = "patents"
    FILINGS = "filings"
    FINANCIALS = "financials"


class JobStage(StrEnum):
    """Lifecycle of a research job. Transitions are persisted per stage."""

    QUEUED = "queued"
    COLLECTING = "collecting"
    VALIDATING = "validating"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class Basis(StrEnum):
    """Provenance class of an analytical claim."""

    SOURCED = "sourced"
    INFERRED = "inferred"
    ASSUMPTION = "assumption"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
