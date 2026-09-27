"""yt-dlp provider — the robust fallback when the API providers are down."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ...config import DEFAULT_USER_AGENT
from .base import MediaResult, ProviderError

logger = logging.getLogger(__name__)

# yt-dlp marks the two TikTok address families differently, depending on the
# release, so we simply score every candidate and prefer the least watermarked.
_WATERMARK_HINTS = ("watermark", "wm_", "play_addr")


class YtDlpProvider:
    """Extract direct media URLs with yt-dlp (imported lazily)."""

    name = "ytdlp"

    def __init__(self, *, user_agent: str = DEFAULT_USER_AGENT, timeout: int = 180) -> None:
        self._user_agent = user_agent
        self._timeout = timeout

    async def fetch(self, url: str) -> MediaResult:
        try:
            import yt_dlp
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise ProviderError(
                "yt-dlp is not installed (pip install yt-dlp)",
                provider=self.name,
                retryable=False,
            ) from exc

        def _extract() -> dict[str, Any]:
            options = {
                "quiet": True,
                "no_warnings": True,
                "noprogress": True,
                "skip_download": True,
                "noplaylist": True,
                "socket_timeout": 30,
                "extractor_retries": 1,
                "http_headers": {"User-Agent": self._user_agent},
                "logger": _QuietLogger(),
            }
            with yt_dlp.YoutubeDL(options) as ydl:
                return ydl.extract_info(url, download=False)

        try:
            info = await asyncio.wait_for(asyncio.to_thread(_extract), timeout=float(self._timeout))
        except TimeoutError as exc:
            raise ProviderError("yt-dlp timed out", provider=self.name) from exc
        except Exception as exc:  # yt-dlp raises a wide variety of errors
            message = str(exc).strip() or exc.__class__.__name__
            retryable = not any(
                token in message.lower()
                for token in ("private", "unavailable", "not found", "removed", "deleted")
            )
            raise ProviderError(message[:200], provider=self.name, retryable=retryable) from exc

        if not info:
            raise ProviderError("yt-dlp returned no data", provider=self.name)

        if info.get("_type") == "playlist":
            entries = [e for e in (info.get("entries") or []) if e]
            if not entries:
                raise ProviderError("yt-dlp found no entries", provider=self.name)
            info = entries[0]

        return self._to_result(info, url)

    # ------------------------------------------------------------------
    def _to_result(self, info: dict[str, Any], source_url: str) -> MediaResult:
        videos = self._pick_videos(info.get("formats") or [])
        images = self._pick_images(info)

        result = MediaResult(
            video_id=str(info.get("id") or "") or None,
            provider=self.name,
            source_url=source_url,
            videos=videos,
            images=images,
            title=str(info.get("title") or info.get("description") or ""),
            author=str(info.get("uploader") or info.get("channel") or "") or None,
            duration=_as_int(info.get("duration")),
            cover=_first_url(info.get("thumbnail")),
            music=str(info.get("track") or info.get("artist") or "") or None,
            size=_as_int(info.get("filesize") or info.get("filesize_approx")),
            hd=_max_height(info.get("formats") or []) >= 720,
            width=_as_int(info.get("width")),
            height=_as_int(info.get("height")),
        )
        if not result.has_media:
            raise ProviderError(
                "yt-dlp found no playable media", provider=self.name, retryable=False
            )
        return result

    @staticmethod
    def _pick_videos(formats: list[dict[str, Any]]) -> list[str]:
        candidates: list[tuple[int, int, int, str]] = []
        for fmt in formats:
            url = fmt.get("url")
            if not url:
                continue
            if fmt.get("vcodec") == "none":  # audio-only stream
                continue
            fingerprint = " ".join(
                str(fmt.get(key) or "") for key in ("format_id", "format_note", "format", "url")
            ).lower()
            watermarked = any(token in fingerprint for token in _WATERMARK_HINTS) and (
                "no_watermark" not in fingerprint
            )
            height = _as_int(fmt.get("height")) or 0
            bitrate = int(float(fmt.get("tbr") or fmt.get("vbr") or 0) or 0)
            score = (0 if watermarked else 1, height, bitrate)
            candidates.append((*score, url))

        candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        seen: set[str] = set()
        ordered: list[str] = []
        for _, _, _, url in candidates:
            if url not in seen:
                seen.add(url)
                ordered.append(url)
        return ordered[:3]

    @staticmethod
    def _pick_images(info: dict[str, Any]) -> list[str]:
        images: list[str] = []
        for entry in info.get("entries") or []:
            if isinstance(entry, dict) and entry.get("url"):
                images.append(entry["url"])
        if not images and info.get("url") and info.get("ext") in {"jpg", "jpeg", "png", "webp"}:
            images.append(info["url"])
        return images[:10]


class _QuietLogger:
    """Swallow yt-dlp's chatty output (we already log through our own logger)."""

    def debug(self, message: str) -> None:
        return None

    def info(self, message: str) -> None:
        return None

    def warning(self, message: str) -> None:
        logger.debug("yt-dlp: %s", message)

    def error(self, message: str) -> None:
        logger.debug("yt-dlp error: %s", message)


def _as_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _first_url(value: Any) -> str | None:
    if isinstance(value, str) and value.startswith("http"):
        return value
    if isinstance(value, list) and value:
        return _first_url(value[0])
    if isinstance(value, dict):
        return _first_url(value.get("url"))
    return None


def _max_height(formats: list[dict[str, Any]]) -> int:
    heights = [_as_int(f.get("height")) or 0 for f in formats]
    return max(heights) if heights else 0
