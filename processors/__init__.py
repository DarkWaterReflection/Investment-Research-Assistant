"""Evidence validation and enrichment pipeline.

Collectors produce raw Evidence; this package turns it into a vetted, scored,
deduplicated corpus. The stages are individually importable, and
``ValidationPipeline`` composes them in the canonical order.
"""

from __future__ import annotations

from processors.cleaning import clean_evidence, clean_text
from processors.conflicts import Conflict, detect_conflicts
from processors.dedupe import DedupeResult, canonicalize_url, dedupe_evidence
from processors.entity_resolution import EntityResolutionResult, resolve_entities
from processors.ner import ExtractedEntities, MoneyMention, extract_entities
from processors.pipeline import ProcessedCorpus, ValidationPipeline
from processors.reliability import apply_confidence, score_confidence
from processors.timeline import TimelineEvent, build_timeline

__all__ = [
    "Conflict",
    "DedupeResult",
    "EntityResolutionResult",
    "ExtractedEntities",
    "MoneyMention",
    "ProcessedCorpus",
    "TimelineEvent",
    "ValidationPipeline",
    "apply_confidence",
    "build_timeline",
    "canonicalize_url",
    "clean_evidence",
    "clean_text",
    "detect_conflicts",
    "dedupe_evidence",
    "extract_entities",
    "resolve_entities",
    "score_confidence",
]
