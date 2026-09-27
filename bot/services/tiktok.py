"""TikTok URL parsing, normalisation and short-link expansion."""

from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import urlsplit

#: Hosts that belong to TikTok (short links use the ``vm``/``vt`` subdomains).
TIKTOK_HOSTS: frozenset[str] = frozenset(
    {
        "tiktok.com",
        "www.tiktok.com",
        "m.tiktok.com",
        "vm.tiktok.com",
        "vt.tiktok.com",
    }
)

_HOST = r"(?:www\.|m\.|vm\.|vt\.)?tiktok\.com"

_URL_RE = re.compile(
    rf"(?<![\w@./-])(?:https?://)?{_HOST}/[^\s<>\"'`]+",
    re.IGNORECASE,
)

# https://www.tiktok.com/@user/video/7123456789012345678
_VIDEO_ID_RE = re.compile(r"/(?:video|photo|v)/(\d{5,30})", re.IGNORECASE)
# https://m.tiktok.com/v/7123456789012345678.html
_LEGACY_ID_RE = re.compile(r"/v/(\d{5,30})(?:\.html?)?", re.IGNORECASE)
# https://vm.tiktok.com/ZMhvzrfeR/  ->  ZMhvzrfeR
_SHORT_ID_RE = re.compile(r"^https://(?:vm|vt)\.tiktok\.com/([A-Za-z0-9_-]{4,64})", re.IGNORECASE)

# Punctuation that usually sticks to a URL when people paste it in chat.
_TRAILING_JUNK = "".join(
    (".", ",", ";", ":", "!", "?", ")", "]", "}", "'", '"', "’", "”", "…", "`", " ")
)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def extract_urls(text: str | None) -> list[str]:
    """Return every TikTok URL found in ``text``, normalised and de-duplicated.

    Order is preserved so the bot answers links in the order the user sent them.
    """
    if not text:
        return []

    found: list[str] = []
    seen: set[str] = set()
    for match in _URL_RE.finditer(text):
        url = normalize_url(match.group(0))
        if not url:
            continue
        key = parse_video_id(url) or url
        if key in seen:
            continue
        seen.add(key)
        found.append(url)
    return found


def normalize_url(url: str) -> str:
    """Turn a raw match into a clean absolute ``https://`` URL."""
    url = (url or "").strip()
    if not url:
        return ""
    url = url.strip(_TRAILING_JUNK + " ")
    if url.startswith("//"):
        url = "https:" + url
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url
    if url.lower().startswith("http://"):
        url = "https://" + url[len("http://") :]
    return url


def is_tiktok_url(url: str) -> bool:
    """True when ``url`` points at a TikTok host."""
    try:
        host = urlsplit(normalize_url(url)).netloc.lower().split("@")[-1].split(":")[0]
    except ValueError:
        return False
    return host in TIKTOK_HOSTS


def is_short_url(url: str) -> bool:
    """True for ``vm.tiktok.com`` / ``vt.tiktok.com`` links."""
    host = urlsplit(normalize_url(url)).netloc.lower()
    return host in {"vm.tiktok.com", "vt.tiktok.com"}


def parse_video_id(url: str) -> str | None:
    """Extract a stable identifier used for caching.

    Long links expose the numeric video id. Short links only expose their code,
    which we namespace with ``short:`` to avoid collisions.
    """
    normalized = normalize_url(url)
    if not normalized:
        return None

    match = _VIDEO_ID_RE.search(normalized) or _LEGACY_ID_RE.search(normalized)
    if match:
        return match.group(1)

    match = _SHORT_ID_RE.match(normalized)
    if match:
        return f"short:{match.group(1)}"
    return None


def author_handle(url: str) -> str | None:
    """Return the ``@handle`` contained in a long TikTok URL (if any)."""
    match = re.search(r"tiktok\.com/@([A-Za-z0-9._-]{2,32})", normalize_url(url), re.IGNORECASE)
    return f"@{match.group(1)}" if match else None


async def expand_short_url(
    url: str,
    session,
    *,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: float = 15.0,
) -> str | None:
    """Follow redirects of a short link and return the canonical URL.

    Returns ``None`` when the expansion fails (TikTok blocks datacenter IPs
    quite often) — callers should simply keep using the short URL.
    """

    from aiohttp import ClientTimeout

    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Range": "bytes=0-0",
    }
    try:
        async with session.get(
            url,
            headers=headers,
            allow_redirects=True,
            timeout=ClientTimeout(total=timeout),
        ) as response:
            final_url = str(response.url)
    except (TimeoutError, OSError, ValueError, Exception):
        return None

    return final_url if is_tiktok_url(final_url) else None


def unique(items: Iterable[str]) -> list[str]:
    """De-duplicate while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
