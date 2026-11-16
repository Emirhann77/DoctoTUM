"""A small per-user sliding-window limit for the routes that spend money (OpenAI)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException

_lock = threading.Lock()
_hits: dict[tuple[str, str], deque] = defaultdict(deque)


def check(user_id: str, bucket: str, limit: int, window_seconds: int) -> None:
    now = time.monotonic()
    with _lock:
        q = _hits[(bucket, user_id)]
        while q and now - q[0] > window_seconds:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.")
        q.append(now)


def reset() -> None:
    with _lock:
        _hits.clear()
