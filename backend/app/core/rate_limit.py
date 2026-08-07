"""Tiny in-memory per-IP sliding-window rate limiter for auth endpoints.

Suitable for a single-process deployment (the current Coolify setup).
If the app is ever scaled horizontally, swap the backing store for Redis —
the call sites will not need to change.
"""

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request

from .config import settings

_hits: dict[tuple[str, str], deque] = defaultdict(deque)
_lock = Lock()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(request: Request, scope: str, max_calls: int) -> None:
    """Raise 429 when the caller exceeded max_calls in the sliding window."""
    if not settings.RATE_LIMIT_ENABLED:
        return

    window = settings.RATE_LIMIT_WINDOW_SECONDS
    now = time.monotonic()
    key = (scope, _client_ip(request))

    with _lock:
        bucket = _hits[key]
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        if len(bucket) >= max_calls:
            raise HTTPException(
                status_code=429,
                detail="Too many attempts. Please wait a few minutes and try again.",
            )
        bucket.append(now)


def reset_rate_limits() -> None:
    """Clear all buckets (used by tests)."""
    with _lock:
        _hits.clear()
