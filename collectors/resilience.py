"""Resilience helpers shared by collectors: retry with exponential backoff.

Rate limiting and circuit breaking move to Redis-backed implementations when
the job queue lands; this module keeps the call-site API stable.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx

T = TypeVar("T")

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


async def with_retries(
    fn: Callable[[], Awaitable[httpx.Response]],
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
) -> httpx.Response:
    """Run an HTTP call, retrying transient failures with jittered backoff.

    Retries connection errors and RETRYABLE_STATUS codes. Once attempts are
    exhausted the final response is returned (not raised), so callers keep
    ownership of status-code interpretation — e.g. mapping a persistent 429
    to RateLimitedError. Raises only when every attempt failed at transport.
    """
    last_exc: Exception | None = None
    last_response: httpx.Response | None = None
    for attempt in range(attempts):
        try:
            response = await fn()
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            last_exc = exc
        else:
            if response.status_code not in RETRYABLE_STATUS:
                return response
            last_response = response
        if attempt < attempts - 1:
            delay = min(max_delay, base_delay * 2**attempt)
            await asyncio.sleep(delay * (0.5 + random.random() / 2))
    if last_response is not None:
        return last_response
    assert last_exc is not None
    raise last_exc
