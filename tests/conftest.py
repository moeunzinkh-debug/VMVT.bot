"""Shared pytest fixtures."""

from __future__ import annotations

from typing import Any

import pytest

from bot.config import Settings
from bot.services.cache import MediaCache
from bot.services.providers.base import MediaResult
from bot.services.rate_limit import RateLimiter


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        bot_token="123456:TEST-TOKEN",
        temp_dir=tmp_path,
        log_level="DEBUG",
    )


@pytest.fixture
def media_cache() -> MediaCache:
    return MediaCache(ttl=60, max_size=10)


@pytest.fixture
def limiter() -> RateLimiter:
    return RateLimiter(max_events=3, period=60)


@pytest.fixture
def video_result() -> MediaResult:
    return MediaResult(
        video_id="7123456789012345678",
        provider="tikwm",
        source_url="https://www.tiktok.com/@khmer.drama/video/7123456789012345678",
        videos=[
            "https://cdn.example.com/hd.mp4",
            "https://cdn.example.com/play.mp4",
            "https://cdn.example.com/wm.mp4",
        ],
        title="រឿងខ្លី • ភាគ ១ #drama #khmer",
        author="khmer.drama",
        duration=95,
        size=4_200_000,
        hd=True,
    )


class FakeResponse:
    """Minimal stand-in for ``aiohttp.ClientResponse`` (JSON APIs)."""

    def __init__(self, payload: Any, status: int = 200, headers: dict[str, str] | None = None):
        self._payload = payload
        self.status = status
        self.headers = headers or {"Content-Type": "application/json"}

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    async def json(self, content_type: Any = None) -> Any:
        return self._payload

    async def text(self) -> str:
        return str(self._payload)


class FakeSession:
    """Records the last call and replays a canned response."""

    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return self.response


class FakeDownloadResponse:
    """Stand-in for a streaming download response."""

    def __init__(
        self,
        chunks: list[bytes],
        status: int = 200,
        *,
        content_type: str = "video/mp4",
        content_length: int | None = None,
    ):
        self.status = status
        self.chunks = chunks
        headers = {"Content-Type": content_type}
        if content_length is not None:
            headers["Content-Length"] = str(content_length)
        self.headers = headers
        self._iterated = False

    async def __aenter__(self) -> FakeDownloadResponse:
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    @property
    def content(self) -> FakeDownloadResponse:
        return self

    async def iter_chunked(self, size: int):
        for chunk in self.chunks:
            yield chunk


class FakeDownloadSession:
    """Returns canned media streams for :meth:`TikTokService.download`."""

    def __init__(self, response: FakeDownloadResponse):
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> FakeDownloadResponse:
        self.calls.append({"url": url, **kwargs})
        return self.response
