"""TikWM provider — fast, free and returns no-watermark + HD links."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientSession, ClientTimeout

from ...config import DEFAULT_USER_AGENT
from .base import MediaResult, ProviderError

TIKWM_ORIGIN = "https://www.tikwm.com"


class TikWMProvider:
    """Resolve TikTok posts through the public TikWM API."""

    name = "tikwm"

    def __init__(
        self,
        session: ClientSession,
        *,
        api_url: str = "https://www.tikwm.com/api/",
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = 30.0,
    ) -> None:
        self._session = session
        self._api_url = api_url
        self._user_agent = user_agent
        self._timeout = timeout

    # ------------------------------------------------------------------
    async def fetch(self, url: str) -> MediaResult:
        payload = {"url": url, "count": 12, "cursor": 0, "web": 1, "hd": 1}
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": TIKWM_ORIGIN,
            "Referer": f"{TIKWM_ORIGIN}/",
            "User-Agent": self._user_agent,
        }

        try:
            async with self._session.post(
                self._api_url,
                data=payload,
                headers=headers,
                timeout=ClientTimeout(total=self._timeout),
            ) as response:
                if response.status >= 500:
                    raise ProviderError(
                        f"TikWM HTTP {response.status}", provider=self.name, retryable=True
                    )
                if response.status >= 400:
                    raise ProviderError(
                        f"TikWM HTTP {response.status}", provider=self.name, retryable=False
                    )
                try:
                    body: dict[str, Any] = await response.json(content_type=None)
                except (TimeoutError, ValueError) as exc:
                    raise ProviderError(
                        "TikWM returned invalid JSON", provider=self.name, retryable=True
                    ) from exc
        except ProviderError:
            raise
        except TimeoutError as exc:
            raise ProviderError("TikWM timed out", provider=self.name, retryable=True) from exc
        except Exception as exc:  # aiohttp raises a wide family of errors
            raise ProviderError(
                f"TikWM request failed: {exc}", provider=self.name, retryable=True
            ) from exc

        code = body.get("code", -1)
        data = body.get("data")
        if code != 0 or not isinstance(data, dict):
            message = str(body.get("msg") or "TikWM could not resolve this link").strip()
            raise ProviderError(message, provider=self.name, retryable=True)

        return self._to_result(data, url)

    # ------------------------------------------------------------------
    def _to_result(self, data: dict[str, Any], source_url: str) -> MediaResult:
        videos = [
            self._absolute(data.get("hdplay")),
            self._absolute(data.get("play")),
            self._absolute(data.get("wmplay")),
        ]
        videos = [v for v in videos if v]

        images = [self._absolute(u) for u in (data.get("images") or []) if isinstance(u, str)]
        images = [i for i in images if i]

        author = data.get("author") or {}
        if not isinstance(author, dict):
            author = {}

        result = MediaResult(
            video_id=str(data.get("id") or "") or None,
            provider=self.name,
            source_url=source_url,
            videos=videos,
            images=images,
            title=str(data.get("title") or ""),
            author=str(author.get("unique_id") or "") or None,
            duration=_as_int(data.get("duration")),
            cover=self._absolute(data.get("cover") or data.get("origin_cover")),
            music=_music_title(data),
            size=_as_int(data.get("size")) or None,
            hd=bool(data.get("hdplay")),
        )
        if not result.has_media:
            raise ProviderError(
                "TikWM returned no media (the post may be private)",
                provider=self.name,
                retryable=False,
            )
        return result

    @staticmethod
    def _absolute(url: Any) -> str:
        """TikWM sometimes returns root-relative or protocol-relative URLs."""
        if not isinstance(url, str) or not url.strip():
            return ""
        url = url.strip()
        if url.startswith("//"):
            return f"https:{url}"
        if url.startswith("/"):
            return f"{TIKWM_ORIGIN}{url}"
        if url.startswith("http"):
            return url
        return ""


def _as_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _music_title(data: dict[str, Any]) -> str | None:
    info = data.get("music_info")
    if isinstance(info, dict):
        for key in ("title", "author", "album"):
            value = info.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    music = data.get("music")
    if isinstance(music, str) and music.strip() and music.strip().lower() != "none":
        return music.strip()
    return None
