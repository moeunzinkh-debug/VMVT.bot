"""Runtime configuration for VMVT.bot.

Every value is read from the environment so the bot can be deployed on
Render (or anywhere else) without touching the source code.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Telegram hard limits (see https://core.telegram.org/bots/api).
TELEGRAM_MAX_VIDEO_BYTES = 50 * 1024 * 1024
# Bot API accepts URL-based video uploads up to 20 MB; larger files need upload.
TELEGRAM_MAX_URL_VIDEO_BYTES = 20 * 1024 * 1024
TELEGRAM_MAX_PHOTO_BYTES = 10 * 1024 * 1024
TELEGRAM_MAX_CAPTION_CHARS = 1024
TELEGRAM_MAX_MEDIA_GROUP = 10


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return default if value is None or value == "" else value


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "y"}


def _env_ids(name: str) -> tuple[int, ...]:
    raw = _env(name)
    if not raw:
        return ()
    ids: list[int] = []
    for chunk in raw.replace(";", ",").split(","):
        chunk = chunk.strip()
        if chunk.isdigit() or (chunk.startswith("-") and chunk[1:].isdigit()):
            ids.append(int(chunk))
    return tuple(ids)


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of the environment configuration."""

    # --- Telegram -------------------------------------------------------
    bot_token: str
    mode: str = "polling"  # "polling" | "webhook"
    webhook_url: str | None = None
    webhook_path: str = "/webhook"
    webhook_secret: str | None = None
    drop_pending_updates: bool = True
    admin_ids: tuple[int, ...] = ()

    # --- HTTP server (health check + webhook) ---------------------------
    host: str = "0.0.0.0"
    port: int = 8080

    # --- Downloading ----------------------------------------------------
    max_upload_mb: int = 48
    download_timeout_s: int = 180
    connect_timeout_s: int = 15
    chunk_bytes: int = 64 * 1024
    user_agent: str = DEFAULT_USER_AGENT
    max_links_per_message: int = 3
    max_slideshow_images: int = TELEGRAM_MAX_MEDIA_GROUP

    # --- Providers ------------------------------------------------------
    tikwm_enabled: bool = True
    tikwm_api_url: str = "https://www.tikwm.com/api/"
    ytdlp_enabled: bool = True
    resolve_cache_ttl: int = 600

    # --- Caching / throttling -------------------------------------------
    media_cache_ttl: int = 6 * 60 * 60
    media_cache_size: int = 500
    rate_limit_per_min: int = 8

    # --- Misc -----------------------------------------------------------
    log_level: str = "INFO"
    temp_dir: Path = field(default_factory=lambda: Path(tempfile.gettempdir()) / "vmvt")

    # ------------------------------------------------------------------
    @classmethod
    def from_env(cls, *, require_token: bool = True) -> Settings:
        """Build :class:`Settings` from environment variables.

        ``require_token=False`` is used by ``python -m bot.serve``, which only
        starts the health endpoint and therefore needs no Telegram token.
        """
        token = _env("BOT_TOKEN") or _env("TELEGRAM_BOT_TOKEN") or _env("TELEGRAM_TOKEN")
        if not token and require_token:
            raise RuntimeError(
                "BOT_TOKEN is not set. Create a bot with @BotFather, then export "
                "BOT_TOKEN=<your token> (or put it in a .env file)."
            )

        webhook_url = _env("WEBHOOK_URL") or _env("PUBLIC_URL")
        use_webhook = _env_bool("USE_WEBHOOK", False)
        if use_webhook and not webhook_url:
            # Render exposes the public hostname through RENDER_EXTERNAL_URL.
            render_url = _env("RENDER_EXTERNAL_URL")
            if render_url:
                webhook_url = render_url.rstrip("/")

        mode = (_env("MODE") or "auto").strip().lower()
        if mode not in {"auto", "polling", "webhook"}:
            mode = "auto"
        if mode == "auto":
            mode = "webhook" if webhook_url and use_webhook else "polling"

        log_level = (_env("LOG_LEVEL") or "INFO").strip().upper()

        return cls(
            bot_token=(token or "").strip(),
            mode=mode,
            webhook_url=webhook_url.rstrip("/") if webhook_url else None,
            webhook_path=_env("WEBHOOK_PATH", "/webhook") or "/webhook",
            webhook_secret=_env("WEBHOOK_SECRET"),
            drop_pending_updates=_env_bool("DROP_PENDING_UPDATES", True),
            admin_ids=_env_ids("ADMIN_IDS"),
            host=_env("HOST", "0.0.0.0") or "0.0.0.0",
            port=_env_int("PORT", 8080),
            max_upload_mb=_env_int("MAX_UPLOAD_MB", 48),
            download_timeout_s=_env_int("DOWNLOAD_TIMEOUT", 180),
            connect_timeout_s=_env_int("CONNECT_TIMEOUT", 15),
            chunk_bytes=_env_int("CHUNK_BYTES", 64 * 1024),
            user_agent=_env("USER_AGENT", DEFAULT_USER_AGENT) or DEFAULT_USER_AGENT,
            max_links_per_message=_env_int("MAX_LINKS_PER_MESSAGE", 3),
            max_slideshow_images=_env_int("MAX_SLIDESHOW_IMAGES", TELEGRAM_MAX_MEDIA_GROUP),
            tikwm_enabled=_env_bool("TIKWM_ENABLED", True),
            tikwm_api_url=_env("TIKWM_API_URL", "https://www.tikwm.com/api/")
            or "https://www.tikwm.com/api/",
            ytdlp_enabled=_env_bool("YTDLP_ENABLED", True),
            resolve_cache_ttl=_env_int("RESOLVE_CACHE_TTL", 600),
            media_cache_ttl=_env_int("MEDIA_CACHE_TTL", 6 * 60 * 60),
            media_cache_size=_env_int("MEDIA_CACHE_SIZE", 500),
            rate_limit_per_min=_env_int("RATE_LIMIT_PER_MIN", 8),
            log_level=log_level,
        )

    # ------------------------------------------------------------------
    @property
    def use_webhook(self) -> bool:
        return self.mode == "webhook"

    @property
    def max_upload_bytes(self) -> int:
        return max(1, self.max_upload_mb) * 1024 * 1024

    def is_admin(self, user_id: int | None) -> bool:
        return user_id is not None and user_id in self.admin_ids

    def webhook_endpoint(self) -> str:
        """Full URL Telegram should POST updates to."""
        base = (self.webhook_url or "").rstrip("/")
        path = self.webhook_path if self.webhook_path.startswith("/") else f"/{self.webhook_path}"
        return f"{base}{path}"
