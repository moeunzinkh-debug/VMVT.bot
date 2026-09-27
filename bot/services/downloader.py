"""Orchestrates the providers: resolve a link, then stream the media to disk."""

from __future__ import annotations

import asyncio
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
    async def download_with_ytdlp(
        self,
        url: str,
        *,
        max_bytes: int,
    ) -> DownloadedFile:
        """Download a TikTok post with yt-dlp when its CDN URL is unavailable.

        TikTok's CDN links can require request headers or expire quickly. yt-dlp
        follows the original post URL and handles those details before returning
        a local file that the bot can upload directly into the chat.
        """
        self.settings.temp_dir.mkdir(parents=True, exist_ok=True)
        prefix = f"vmvt-ytdlp-{time.time_ns()}"
        output_template = str(self.settings.temp_dir / f"{prefix}.%(ext)s")

        def _download() -> Path:
            try:
                import yt_dlp
            except ImportError as exc:  # pragma: no cover - declared dependency
                raise DownloadError("yt-dlp is not installed") from exc

            options = {
                "quiet": True,
                "no_warnings": True,
                "noprogress": True,
                "noplaylist": True,
                "format": "best[ext=mp4]/best",
                "merge_output_format": "mp4",
                "max_filesize": max_bytes,
                "socket_timeout": min(60, self.settings.download_timeout_s),
                "retries": 2,
                "http_headers": {"User-Agent": self.settings.user_agent},
                "outtmpl": output_template,
            }
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([url])

            files = [
                path
                for path in self.settings.temp_dir.glob(f"{prefix}.*")
                if path.is_file() and not path.name.endswith((".part", ".ytdl"))
            ]
            if not files:
                raise DownloadError("yt-dlp did not produce a video file")
            return max(files, key=lambda path: path.stat().st_size)

        keep_path: Path | None = None
        try:
            path = await asyncio.wait_for(
                asyncio.to_thread(_download), timeout=self.settings.download_timeout_s
            )
            size = path.stat().st_size
            if size > max_bytes:
                raise MediaTooLargeError("Media exceeds upload limit", size)
            if size == 0:
                raise DownloadError("Downloaded video is empty")
            content_type = "video/mp4" if path.suffix.lower() == ".mp4" else "video/octet-stream"
            keep_path = path
            return DownloadedFile(path=path, size=size, content_type=content_type, url=url)
        except MediaTooLargeError:
            raise
        except DownloadError:
            raise
        except TimeoutError as exc:
            raise DownloadError("yt-dlp download timed out") from exc
        except Exception as exc:
            message = str(exc).strip() or exc.__class__.__name__
            if "file is larger than" in message.lower() or "max_filesize" in message.lower():
                raise MediaTooLargeError(message, max_bytes + 1) from exc
            raise DownloadError(f"yt-dlp download failed: {message[:200]}") from exc
        finally:
            # Keep only the returned file; discard yt-dlp sidecars and partials.
            for extra in self.settings.temp_dir.glob(f"{prefix}.*"):
                if extra != keep_path:
                    try:
                        extra.unlink(missing_ok=True)
                    except OSError:
                        logger.debug("Could not remove yt-dlp temporary file %s", extra)

    # ------------------------------------------------------------------
    def stats(self) -> dict[str, Any]:
        return {
            "providers": [p.name for p in self._providers],
            "resolve_cache": len(self._resolve_cache),
        }
