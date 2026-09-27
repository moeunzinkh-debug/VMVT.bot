"""Per-user sliding-window rate limiter."""

from __future__ import annotations

import time
from collections import defaultdict, deque


class RateLimiter:
    """Allow at most ``max_events`` per ``period`` seconds for each user.

    ``check`` returns ``0.0`` when the request is allowed, otherwise the number
    of seconds the caller must wait before retrying.
    """

    def __init__(self, max_events: int, period: float = 60.0, *, max_users: int = 10_000) -> None:
        self.max_events = max(1, int(max_events))
        self.period = max(1.0, float(period))
        self.max_users = max(1, int(max_users))
        self._hits: dict[int, deque[float]] = defaultdict(deque)

    def check(self, user_id: int, now: float | None = None) -> float:
        now = time.monotonic() if now is None else now
        hits = self._hits[user_id]
        self._evict_old(hits, now)

        if len(hits) >= self.max_events:
            return max(0.0, self.period - (now - hits[0]))

        hits.append(now)
        self._enforce_size_limit()
        return 0.0

    def reset(self, user_id: int) -> None:
        self._hits.pop(user_id, None)

    def _evict_old(self, hits: deque[float], now: float) -> None:
        while hits and (now - hits[0]) >= self.period:
            hits.popleft()

    def _enforce_size_limit(self) -> None:
        if len(self._hits) <= self.max_users:
            return
        # Drop the least recently used buckets.
        for key in sorted(self._hits, key=lambda k: self._hits[k][-1] if self._hits[k] else 0.0)[
            : max(1, len(self._hits) - self.max_users)
        ]:
            self._hits.pop(key, None)

    def __len__(self) -> int:
        return len(self._hits)
