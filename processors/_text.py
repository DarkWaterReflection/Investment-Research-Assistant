"""Internal text utilities shared across processors.

Token-based similarity is used by dedupe, reliability corroboration, and
conflict detection. Kept private (leading underscore) — not part of the
package's public contract.
"""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> set[str]:
    """Lowercase word/number tokens as a set, for order-insensitive overlap."""
    return set(_TOKEN_RE.findall(text.lower()))


def jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity of two token sets; 0.0 when both are empty."""
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def content_similarity(left: str, right: str) -> float:
    """Normalized-token Jaccard similarity between two blobs of text."""
    return jaccard(tokenize(left), tokenize(right))
