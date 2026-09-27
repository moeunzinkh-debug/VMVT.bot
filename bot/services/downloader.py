"""Orchestrates the providers: resolve a link, then stream the media to disk."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from ..config import Settings
from . import tiktok as tiktok_links
from .cache import TTLCache
from .providers import MediaResult, ProviderError, TikWMProvider, YtDlpProvider

logger = logging.getLogger(__name__)

CONTENT_TYPE_PREFIXES = ("video/", "image/", "application/octet-stream", "application/mp4")


class ResolveError(Exception):
    """Raised when no provider could resolve the link."""

    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


class DownloadError(Exception):
    """Raised when a media file could not be fetched."""


class MediaTooLargeError(DownloadError):
    def __init__(self, message: str, size: int | None = None):
        super().__init__(message)
        self.size = size


@dataclass(slots=True)
class DownloadedFile:
    path: Path
    size: int
    content_type: str
    url: str

    @property
    def is_image(self) -> bool:
        return self.content_type.startswith("image/")

    def cleanup(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError:  # pragma: no cover - best effort
            logger.debug("Could not delete temp file %s", self.path)


class TikTokService:
    """High level facade used by the Telegram handlers."""

    def __init__(self, settings: Settings, session: ClientSession) -> None:
        self.settings = settings
        self.session = session
        self._resolve_cache: TTLCache[MediaResult] = TTLCache(
            ttl=settings.resolve_cache_ttl, max_size=500
        )
        self._providers: list[Any] = []
        if settings.tikwm_enabled:
            self._providers.append(
                TikWMProvider(
                    session,
                    api_url=settings.tikwm_api_url,
                    user_agent=settings.user_agent,
                    timeout=float(settings.connect_timeout_s + 25),
                )
            )
        if settings.ytdlp_enabled:
            self._providers.append(YtDlpProvider(user_agent=settings.user_agent))

    # ------------------------------------------------------------------
    async def resolve(self, url: str) -> MediaResult:
        """Return the media for ``url``, trying each provider in order."""
        url = tiktok_links.normalize_url(url)
        cache_key = tiktok_links.parse_video_id(url) or url

        cached = self._resolve_cache.get(cache_key)
        if cached is not None:
            logger.debug("Resolve cache hit for %s", cache_key)
            return cached

        errors: list[str] = []
        retryable = False
        for provider in self._providers:
            started = time.monotonic()
            try:
                result = await provider.fetch(url)
            except ProviderError as exc:
                logger.warning("Provider %s failed for %s: %s", provider.name, url, exc)
                errors.append(f"{provider.name}: {exc}")
                retryable = retryable or exc.retryable
                continue
            logger.info(
                "Provider %s resolved %s in %.1fs (%s)",
                provider.name,
                url,
                time.monotonic() - started,
                result.to_debug_dict(),
            )
            self._resolve_cache.put(cache_key, result)
            return result

        if not self._providers:
            raise ResolveError("No download providers are enabled", retryable=False)
        raise ResolveError("; ".join(errors) or "unknown error", retryable=retryable)

    # ------------------------------------------------------------------
    async def download(
        self,
        url: str,
        *,
        max_bytes: int,
        suffix: str = ".mp4",
    ) -> DownloadedFile:
        """Stream ``url`` into a temporary file, enforcing ``max_bytes``."""
        settings = self.settings
        self.settings.temp_dir.mkdir(parents=True, exist_ok=True)
        timeout = ClientTimeout(
            total=settings.download_timeout_s,
            connect=settings.connect_timeout_s,
            sock_read=60,
        )
        headers = {
            "User-Agent": settings.user_agent,
            "Accept": "video/*,image/*,*/*;q=0.8",
            "Referer": "https://www.tiktok.com/",
        }

        try:
            async with self.session.get(
                url, headers=headers, timeout=timeout, allow_redirects=True
            ) as response:
                if response.status >= 400:
                    raise DownloadError(f"HTTP {response.status} while downloading media")

                content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip()
                if content_type and not content_type.startswith(CONTENT_TYPE_PREFIXES):
                    raise DownloadError(f"Unexpected content type: {content_type}")

                declared = response.headers.get("Content-Length")
                if declared and declared.isdigit() and int(declared) > max_bytes:
                    raise MediaTooLargeError(
                        f"Media is {int(declared)} bytes (limit {max_bytes})", int(declared)
                    )

                path = Path(self.settings.temp_dir) / f"vmvt-{time.time_ns()}-{id(url) % 9973}"
                path = path.with_suffix(suffix)
                written = 0
                try:
                    with path.open("wb") as handle:
                        async for chunk in response.content.iter_chunked(settings.chunk_bytes):
                            written += len(chunk)
                            if written > max_bytes:
                                raise MediaTooLargeError(
                                    f"Media exceeds {max_bytes} bytes", written
                                )
                            handle.write(chunk)
                except MediaTooLargeError:
                    path.unlink(missing_ok=True)
                    raise

                if written == 0:
                    path.unlink(missing_ok=True)
                    raise DownloadError("Downloaded file is empty")

                return DownloadedFile(path=path, size=written, content_type=content_type, url=url)
        except (TimeoutError, ClientError, OSError) as exc:
            raise DownloadError(f"Network error: {exc}") from exc

    # ------------------------------------------------------------------
    def stats(self) -> dict[str, Any]:
        return {
            "providers": [p.name for p in self._providers],
            "resolve_cache": len(self._resolve_cache),
        }
