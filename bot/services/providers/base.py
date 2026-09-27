"""Shared data model for every download provider."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ProviderError(Exception):
    """Raised when a provider cannot resolve a TikTok link."""

    def __init__(
        self,
        message: str,
        *,
        provider: str = "unknown",
        retryable: bool = True,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.retryable = retryable


@dataclass(slots=True)
class MediaResult:
    """Everything the bot needs to deliver a TikTok post."""

    video_id: str | None
    provider: str
    source_url: str
    videos: list[str] = field(default_factory=list)  # best quality first
    images: list[str] = field(default_factory=list)
    title: str = ""
    author: str | None = None
    duration: int | None = None
    cover: str | None = None
    music: str | None = None
    size: int | None = None
    hd: bool = False
    width: int | None = None
    height: int | None = None

    # ------------------------------------------------------------------
    @property
    def is_slideshow(self) -> bool:
        return bool(self.images) and not self.videos

    @property
    def has_media(self) -> bool:
        return bool(self.videos) or bool(self.images)

    @property
    def best_video(self) -> str | None:
        return self.videos[0] if self.videos else None

    @property
    def author_handle(self) -> str | None:
        handle = (self.author or "").strip()
        if not handle:
            return None
        return handle if handle.startswith("@") else f"@{handle}"

    @property
    def profile_url(self) -> str | None:
        handle = self.author_handle
        return f"https://www.tiktok.com/{handle}" if handle else None

    def video_candidates(self, limit: int = 3) -> list[str]:
        """Deduplicated list of playable URLs, best quality first."""
        seen: set[str] = set()
        result: list[str] = []
        for url in self.videos:
            if url and url not in seen:
                seen.add(url)
                result.append(url)
            if len(result) >= limit:
                break
        return result

    def to_debug_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "video_id": self.video_id,
            "has_video": bool(self.videos),
            "images": len(self.images),
            "hd": self.hd,
            "author": self.author,
        }
