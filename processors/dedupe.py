"""Deduplication of Evidence by canonical URL and near-identical content.

The same story reaches us from several collectors and mirrors. Deduplication
collapses those into one representative — the most reliable copy — while
recording every merge so provenance is never silently lost.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, Field

from collectors.base import Evidence
from processors._text import content_similarity

_CONTENT_SIMILARITY_THRESHOLD = 0.9
_TRACKING_PARAM_PREFIXES = ("utm_",)
_TRACKING_PARAMS = frozenset({"gclid", "fbclid", "ref"})


class DedupeResult(BaseModel):
    """Kept representatives plus a record of every dropped -> kept merge."""

    kept: list[Evidence] = Field(default_factory=list)
    merged: list[tuple[str, str]] = Field(default_factory=list)


def _is_tracking_param(key: str) -> bool:
    lowered = key.lower()
    if lowered in _TRACKING_PARAMS:
        return True
    return any(lowered.startswith(prefix) for prefix in _TRACKING_PARAM_PREFIXES)


def canonicalize_url(url: str) -> str:
    """Normalize a URL for equality: lowercase scheme/host, no fragment,
    no trailing slash, tracking parameters stripped.
    """
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path
    if path.endswith("/") and path != "/":
        path = path.rstrip("/")
    kept_params = [
        (key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not _is_tracking_param(key)
    ]
    query = urlencode(kept_params)
    return urlunsplit((scheme, netloc, path, query, ""))


def _duplicates(left: Evidence, right: Evidence) -> bool:
    if canonicalize_url(left.source_url) == canonicalize_url(right.source_url):
        return True
    similarity = content_similarity(left.content, right.content)
    return similarity >= _CONTENT_SIMILARITY_THRESHOLD


def _prefers(candidate: Evidence, incumbent: Evidence) -> bool:
    """True if ``candidate`` should win over ``incumbent`` as representative."""
    if candidate.reliability != incumbent.reliability:
        return candidate.reliability > incumbent.reliability
    return candidate.collected_at < incumbent.collected_at


def dedupe_evidence(evidence: list[Evidence]) -> DedupeResult:
    """Collapse duplicate Evidence, keeping the most reliable copy of each.

    Duplicates share a canonical URL or have normalized-token Jaccard content
    similarity >= 0.9. Within a duplicate cluster the highest-reliability item
    wins (ties broken by earliest ``collected_at``).
    """
    parent = list(range(len(evidence)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        parent[find(i)] = find(j)

    for i in range(len(evidence)):
        for j in range(i + 1, len(evidence)):
            if find(i) != find(j) and _duplicates(evidence[i], evidence[j]):
                union(i, j)

    winner_by_root: dict[int, int] = {}
    for index, item in enumerate(evidence):
        root = find(index)
        current = winner_by_root.get(root)
        if current is None or _prefers(item, evidence[current]):
            winner_by_root[root] = index

    kept: list[Evidence] = []
    merged: list[tuple[str, str]] = []
    for index, item in enumerate(evidence):
        winner_index = winner_by_root[find(index)]
        if index == winner_index:
            kept.append(item)
        else:
            merged.append((item.id, evidence[winner_index].id))
    return DedupeResult(kept=kept, merged=merged)
