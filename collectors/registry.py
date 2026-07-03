"""Collector registry: maps provider names to collector factories.

The orchestrator asks the registry for "all enabled collectors" — enabled
means the provider's credentials are present in Settings (or it needs none).
"""

from __future__ import annotations

from collections.abc import Callable

import httpx

from collectors.base import BaseCollector
from core.config import Settings

CollectorFactory = Callable[[httpx.AsyncClient, Settings], BaseCollector | None]
"""Returns a collector, or None when its credentials are absent."""

_REGISTRY: dict[str, CollectorFactory] = {}


def register(name: str) -> Callable[[CollectorFactory], CollectorFactory]:
    def decorator(factory: CollectorFactory) -> CollectorFactory:
        if name in _REGISTRY:
            raise ValueError(f"Collector {name!r} already registered")
        _REGISTRY[name] = factory
        return factory

    return decorator


def registered_names() -> list[str]:
    return sorted(_REGISTRY)


def build_enabled(
    client: httpx.AsyncClient,
    settings: Settings,
    only: set[str] | None = None,
) -> list[BaseCollector]:
    """Instantiate every registered collector whose requirements are met.

    `only` restricts to a subset (per-request provider selection).
    """
    collectors: list[BaseCollector] = []
    for name, factory in sorted(_REGISTRY.items()):
        if only is not None and name not in only:
            continue
        collector = factory(client, settings)
        if collector is not None:
            collectors.append(collector)
    return collectors
