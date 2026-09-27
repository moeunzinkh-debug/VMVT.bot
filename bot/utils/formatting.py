"""Small formatting helpers shared by the handlers."""

from __future__ import annotations

import html
import re

from ..config import TELEGRAM_MAX_CAPTION_CHARS
from ..services.providers.base import MediaResult

_WHITESPACE_RE = re.compile(r"[ \t ]+")
_ZERO_WIDTH_RE = re.compile(r"[​-‏  ﻿]")


def clean_text(value: str | None) -> str:
    """Collapse whitespace and strip zero-width characters."""
    if not value:
        return ""
    text = _ZERO_WIDTH_RE.sub("", value)
    return _WHITESPACE_RE.sub(" ", text).strip()


def truncate(value: str, limit: int) -> str:
    """Shorten ``value`` to ``limit`` characters, adding an ellipsis."""
    value = clean_text(value)
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def escape_html(value: str | None) -> str:
    """Escape text so it is safe inside an HTML-formatted Telegram message."""
    return html.escape(clean_text(value))


def human_bytes(size: int | float | None) -> str:
    """Return a human readable size, e.g. ``3.4 MB``."""
    if size is None:
        return "?"
    try:
        size = float(size)
    except (TypeError, ValueError):
        return "?"
    if size <= 0:
        return "0 B"
    units = ("B", "KB", "MB", "GB")
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    return f"{size:.0f} {units[index]}" if index == 0 else f"{size:.1f} {units[index]}"


def human_duration(seconds: int | float | None) -> str:
    """Return a ``m:ss`` / ``h:mm:ss`` duration string."""
    if seconds is None:
        return "?"
    try:
        seconds = int(float(seconds))
    except (TypeError, ValueError):
        return "?"
    if seconds < 0:
        return "?"
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def build_caption(result: MediaResult, quality: str | None = None) -> str:
    """Build an HTML caption for a downloaded TikTok post."""
    lines: list[str] = []

    title = truncate(result.title, 180)
    if title:
        lines.append(f"🎬 <b>{escape_html(title)}</b>")

    author = (result.author or "").lstrip("@").strip()
    if author:
        profile = f"https://www.tiktok.com/@{author}"
        lines.append(f'👤 <a href="{html.escape(profile, quote=True)}">@{escape_html(author)}</a>')

    meta: list[str] = []
    if result.duration:
        meta.append(f"⏱ {human_duration(result.duration)}")
    if quality:
        meta.append(quality)
    elif result.hd:
        meta.append("🎞 HD")
    if result.size:
        meta.append(f"💾 {human_bytes(result.size)}")
    if meta:
        lines.append(" • ".join(meta))

    lines.append("───────────")
    lines.append("🤖 VMVT.bot • គ្មាន Watermark ✅")

    caption = "\n".join(lines)
    return caption[:TELEGRAM_MAX_CAPTION_CHARS]
