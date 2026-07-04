"""Text cleaning for raw Evidence payloads.

Collectors emit content that may contain HTML markup, entity escapes, and
control characters. Cleaning normalizes that text without ever mutating the
input record — every transform returns a fresh copy so the original bytes stay
auditable.
"""

from __future__ import annotations

import html
import re

from collectors.base import Evidence

_TAG_RE = re.compile(r"<[^>]+>")
# Control chars except common whitespace (tab, newline, carriage return).
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE_RE = re.compile(r"\s+")


def strip_html(text: str) -> str:
    """Remove HTML tags and unescape entities from a string."""
    without_tags = _TAG_RE.sub(" ", text)
    return html.unescape(without_tags)


def normalize_whitespace(text: str) -> str:
    """Drop control characters and collapse runs of whitespace to a space."""
    without_control = _CONTROL_RE.sub("", text)
    collapsed = _WHITESPACE_RE.sub(" ", without_control)
    return collapsed.strip()


def clean_text(text: str) -> str:
    """Full cleaning pass: strip markup, unescape, normalize whitespace."""
    return normalize_whitespace(strip_html(text))


def clean_evidence(evidence: Evidence) -> Evidence:
    """Return a cleaned copy of ``evidence``; never mutates the input.

    Content has HTML stripped and whitespace/control characters normalized;
    the title is stripped of markup and surrounding whitespace.
    """
    return evidence.model_copy(
        update={
            "title": clean_text(evidence.title),
            "content": clean_text(evidence.content),
        }
    )
