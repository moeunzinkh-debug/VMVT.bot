"""Tiny in-process caches (no Redis needed on the Render free plan)."""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class TTLCache(Generic[K, V]):
    """Very small TTL + LRU cache. Process local, intentionally boring."""

    def __init__(self, ttl: float, max_size: int = 256) -> None:
        self._ttl = max(0.0, float(ttl))
        self._max_size = max(1, int(max_size))
        self._data: OrderedDict[K, tuple[float, V]] = OrderedDict()

    def get(self, key: K) -> V | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        created, value = entry
        if self._ttl and (time.monotonic() - created) > self._ttl:
            self._data.pop(key, None)
            return None
        self._data.move_to_end(key)
        return value

    def put(self, key: K, value: V) -> None:
        self._data[key] = (time.monotonic(), value)
        self._data.move_to_end(key)
        while len(self._data) > self._max_size:
            self._data.popitem(last=False)

    def invalidate(self, key: K) -> None:
        self._data.pop(key, None)

    def clear(self) -> None:
        self._data.clear()

    def prune(self) -> int:
        """Drop expired entries. Returns the number of removed items."""
        if not self._ttl:
            return 0
        now = time.monotonic()
        expired = [k for k, (created, _) in self._data.items() if now - created > self._ttl]
        for key in expired:
            self._data.pop(key, None)
        return len(expired)

    def __len__(self) -> int:
        return len(self._data)


@dataclass(slots=True)
class CachedMedia:
    """A Telegram ``file_id`` we can reuse instead of re-uploading."""

    file_id: str
    kind: str  # "video" | "photo"
    created: float


class MediaCache(TTLCache[str, CachedMedia]):
    """Maps a TikTok id to an already-uploaded Telegram file id."""

    def remember_video(self, key: str, file_id: str) -> None:
        self.put(key, CachedMedia(file_id=file_id, kind="video", created=time.time()))

    def remember_photo(self, key: str, file_id: str) -> None:
        self.put(key, CachedMedia(file_id=file_id, kind="photo", created=time.time()))
