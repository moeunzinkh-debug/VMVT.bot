"""Tests for the in-process caches and the rate limiter."""

from __future__ import annotations

import time

from bot.services.cache import CachedMedia, MediaCache, TTLCache
from bot.services.rate_limit import RateLimiter


def test_ttl_cache_expires_entries() -> None:
    cache: TTLCache[str, str] = TTLCache(ttl=10, max_size=5)
    cache.put("a", "1")
    assert cache.get("a") == "1"

    # simulate the entry being created far in the past
    key = next(iter(cache._data))
    old_time, value = cache._data[key]
    cache._data[key] = (old_time - 100, value)
    assert cache.get("a") is None
    assert len(cache) == 0


def test_ttl_cache_respects_max_size() -> None:
    cache: TTLCache[str, str] = TTLCache(ttl=60, max_size=3)
    for index in range(5):
        cache.put(f"k{index}", str(index))
    assert len(cache) == 3
    assert cache.get("k0") is None  # evicted (LRU)
    assert cache.get("k4") == "4"


def test_ttl_cache_prune_and_clear() -> None:
    cache: TTLCache[str, str] = TTLCache(ttl=1, max_size=10)
    cache.put("a", "1")
    cache.put("b", "2")
    assert cache.prune() == 0
    time.sleep(1.1)
    assert cache.prune() == 2
    cache.put("c", "3")
    cache.clear()
    assert len(cache) == 0


def test_media_cache_remembers_file_ids() -> None:
    cache = MediaCache(ttl=60, max_size=2)
    cache.remember_video("7123456789012345678", "FILE_ID_1")
    cache.remember_photo("999", "PHOTO_ID")

    assert cache.get("7123456789012345678").file_id == "FILE_ID_1"
    assert cache.get("7123456789012345678").kind == "video"
    assert cache.get("999").kind == "photo"
    assert isinstance(cache.get("999"), CachedMedia)

    cache.invalidate("999")
    assert cache.get("999") is None


def test_rate_limiter_allows_burst_then_blocks() -> None:
    limiter = RateLimiter(max_events=3, period=60)
    now = 1_000.0

    assert limiter.check(7, now=now) == 0.0
    assert limiter.check(7, now=now + 1) == 0.0
    assert limiter.check(7, now=now + 2) == 0.0

    wait = limiter.check(7, now=now + 3)
    assert wait > 0

    # another user is unaffected
    assert limiter.check(8, now=now + 3) == 0.0


def test_rate_limiter_window_slides() -> None:
    limiter = RateLimiter(max_events=2, period=10)
    assert limiter.check(1, now=100.0) == 0.0
    assert limiter.check(1, now=101.0) == 0.0
    assert limiter.check(1, now=102.0) > 0

    # after the window has passed the user can send again
    assert limiter.check(1, now=111.0) == 0.0


def test_rate_limiter_reset_and_size() -> None:
    limiter = RateLimiter(max_events=1, period=60)
    limiter.check(1, now=1.0)
    assert len(limiter) == 1
    limiter.reset(1)
    assert len(limiter) == 0
    assert limiter.check(1, now=1.0) == 0.0


def test_rate_limiter_caps_tracked_users() -> None:
    limiter = RateLimiter(max_events=5, period=60, max_users=3)
    for user_id in range(10):
        limiter.check(user_id, now=float(user_id))
    assert len(limiter) <= 3
