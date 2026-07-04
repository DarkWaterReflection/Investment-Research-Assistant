"""Entity resolution: keep evidence that is actually about the target.

Name collisions are the quiet killer of automated research — "Apple" the fruit
supplier, a namesake startup, a same-named person. Evidence that does not tie
back to the target is quarantined, not discarded: it is real evidence about the
*wrong* entity, and that distinction is worth preserving.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from pydantic import BaseModel, Field

from collectors.base import CompanyTarget, Evidence


class EntityResolutionResult(BaseModel):
    """Evidence partitioned into what matches the target and what does not."""

    matched: list[Evidence] = Field(default_factory=list)
    quarantined: list[Evidence] = Field(default_factory=list)


def _host(url: str) -> str:
    host = urlsplit(url.strip()).netloc.lower()
    # Drop credentials and port if present.
    if "@" in host:
        host = host.rsplit("@", 1)[1]
    if ":" in host:
        host = host.split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def _domain_matches(source_url: str, target: CompanyTarget) -> bool:
    if target.website is None:
        return False
    target_host = _host(str(target.website))
    source_host = _host(source_url)
    if not target_host or not source_host:
        return False
    return source_host == target_host or source_host.endswith("." + target_host)


def _mentions(haystack: str, terms: list[str]) -> bool:
    lowered = haystack.lower()
    return any(term and term.lower() in lowered for term in terms)


def resolve_entities(
    evidence: list[Evidence], target: CompanyTarget
) -> EntityResolutionResult:
    """Partition ``evidence`` into items about ``target`` and quarantined items.

    An item matches when its title or content mentions the target name or any
    alias (case-insensitive), or when its source URL host matches the target
    website domain.
    """
    terms = [target.name, *target.aliases]
    matched: list[Evidence] = []
    quarantined: list[Evidence] = []
    for item in evidence:
        text = f"{item.title}\n{item.content}"
        if _mentions(text, terms) or _domain_matches(item.source_url, target):
            matched.append(item)
        else:
            quarantined.append(item)
    return EntityResolutionResult(matched=matched, quarantined=quarantined)
