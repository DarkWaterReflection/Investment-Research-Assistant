"""Rule-based named-entity extraction — INTERIM.

This module extracts money amounts, dates, organizations, and people using
hand-written patterns. It is deliberately dependency-free (no spaCy / model
downloads) so CI stays hermetic. Precision is favored over recall: it is a
placeholder to be replaced by a proper statistical NER model, and every
heuristic here is a known approximation, not a finished classifier.
"""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #


class MoneyMention(BaseModel):
    """A monetary amount normalized to a base-unit float plus its raw text."""

    amount: float
    currency: str
    raw: str


class ExtractedEntities(BaseModel):
    """Entities pulled from a block of free text."""

    money: list[MoneyMention] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    orgs: list[str] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Money
# --------------------------------------------------------------------------- #

_CURRENCY_SYMBOLS: dict[str, str] = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}
_CURRENCY_CODES: frozenset[str] = frozenset(
    {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "CNY", "INR", "RMB"}
)
_MULTIPLIERS: dict[str, float] = {
    "thousand": 1e3,
    "million": 1e6,
    "billion": 1e9,
    "trillion": 1e12,
    "mm": 1e6,
    "bn": 1e9,
    "tn": 1e12,
    "k": 1e3,
    "m": 1e6,
    "b": 1e9,
    "t": 1e12,
}

_MONEY_RE = re.compile(
    r"(?P<cur>[$€£¥]|\b(?:USD|EUR|GBP|JPY|CHF|CAD|AUD|CNY|INR|RMB)\b)\s*"
    r"(?P<num>\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?|\.\d+)\s*"
    r"(?P<mult>thousand|million|billion|trillion|mm|bn|tn|[kmbt])?\b",
    re.IGNORECASE,
)


def _normalize_currency(token: str) -> str:
    token = token.strip()
    if token in _CURRENCY_SYMBOLS:
        return _CURRENCY_SYMBOLS[token]
    return token.upper()


def _extract_money(text: str) -> list[MoneyMention]:
    mentions: list[MoneyMention] = []
    for match in _MONEY_RE.finditer(text):
        code = match.group("cur").upper()
        if code not in _CURRENCY_SYMBOLS and code not in _CURRENCY_CODES:
            continue
        number = float(match.group("num").replace(",", ""))
        mult_token = match.group("mult")
        multiplier = _MULTIPLIERS[mult_token.lower()] if mult_token else 1.0
        mentions.append(
            MoneyMention(
                amount=number * multiplier,
                currency=_normalize_currency(match.group("cur")),
                raw=match.group(0).strip(),
            )
        )
    return mentions


# --------------------------------------------------------------------------- #
# Dates
# --------------------------------------------------------------------------- #

_MONTHS: dict[str, int] = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9, "october": 10,
    "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}

_MONTH_ALT = "|".join(sorted(_MONTHS, key=len, reverse=True))

_ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_US_SLASH_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_ISO_SLASH_RE = re.compile(r"\b(\d{4})/(\d{1,2})/(\d{1,2})\b")
_MONTH_FIRST_RE = re.compile(
    rf"\b({_MONTH_ALT})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b",
    re.IGNORECASE,
)
_DAY_FIRST_RE = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_ALT})\.?,?\s+(\d{{4}})\b",
    re.IGNORECASE,
)


def _iso_or_none(year: int, month: int, day: int) -> str | None:
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")  # noqa: DTZ001
    except ValueError:
        return None


def _extract_dates(text: str) -> list[str]:
    found: list[tuple[int, int, str]] = []

    def add(start: int, end: int, iso: str | None) -> None:
        if iso is not None:
            found.append((start, end, iso))

    for m in _ISO_RE.finditer(text):
        add(m.start(), m.end(), _iso_or_none(int(m[1]), int(m[2]), int(m[3])))
    for m in _ISO_SLASH_RE.finditer(text):
        add(m.start(), m.end(), _iso_or_none(int(m[1]), int(m[2]), int(m[3])))
    for m in _US_SLASH_RE.finditer(text):
        add(m.start(), m.end(), _iso_or_none(int(m[3]), int(m[1]), int(m[2])))
    for m in _MONTH_FIRST_RE.finditer(text):
        add(m.start(), m.end(), _iso_or_none(int(m[3]), _MONTHS[m[1].lower()], int(m[2])))
    for m in _DAY_FIRST_RE.finditer(text):
        add(m.start(), m.end(), _iso_or_none(int(m[3]), _MONTHS[m[2].lower()], int(m[1])))

    found.sort(key=lambda item: item[0])
    result: list[str] = []
    consumed_end = -1
    for start, end, iso in found:
        if start >= consumed_end:
            result.append(iso)
            consumed_end = end
    return result


# --------------------------------------------------------------------------- #
# Organizations
# --------------------------------------------------------------------------- #

_ORG_SUFFIXES = (
    "Incorporated", "Inc", "Corporation", "Corp", "Company", "Co", "Limited",
    "Ltd", "LLC", "LLP", "PLC", "Ventures", "Capital", "Partners", "Holdings",
    "Group", "Technologies", "Labs", "Systems", "Solutions", "Foundation",
    "Bank", "GmbH", "AG", "SA", "NV", "Fund",
)
_ORG_SUFFIX_ALT = "|".join(_ORG_SUFFIXES)
_ORG_RE = re.compile(
    rf"\b((?:[A-Z][\w&.\-]*\s+){{1,5}}(?:{_ORG_SUFFIX_ALT})\.?)(?!\w)"
)


def _dedupe_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.strip()
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result


def _extract_orgs(text: str) -> list[str]:
    return _dedupe_preserve([m.group(1).strip(" .") for m in _ORG_RE.finditer(text)])


# --------------------------------------------------------------------------- #
# People
# --------------------------------------------------------------------------- #

_TITLE = (
    r"(?:CEO|CTO|CFO|COO|CMO|CIO|[Ff]ounder|[Cc]o-?[Ff]ounder|"
    r"[Pp]resident|[Cc]hair(?:man|woman|person)?|"
    r"[Cc]hief\s+\w+\s+[Oo]fficer|[Dd]irector|[Pp]artner)"
)
_NAME = r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}"
_TITLE_FIRST_RE = re.compile(rf"{_TITLE}[,:]?\s+(?:of\s+\w+\s+)?({_NAME})")
_NAME_FIRST_RE = re.compile(rf"({_NAME}),?\s+(?:the\s+)?{_TITLE}\b")


def _extract_people(text: str) -> list[str]:
    people = [m.group(1) for m in _TITLE_FIRST_RE.finditer(text)]
    people += [m.group(1) for m in _NAME_FIRST_RE.finditer(text)]
    return _dedupe_preserve(people)


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def extract_entities(text: str) -> ExtractedEntities:
    """Extract money, dates, organizations, and people from ``text``.

    Rule-based and interim; see the module docstring. Returns structured
    mentions with the original substrings preserved for audit.
    """
    return ExtractedEntities(
        money=_extract_money(text),
        dates=_extract_dates(text),
        orgs=_extract_orgs(text),
        people=_extract_people(text),
    )
