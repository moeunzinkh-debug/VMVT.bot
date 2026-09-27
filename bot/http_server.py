"""aiohttp server that serves the health check, a status page and (optionally)
the Telegram webhook on a single port.

Render's free plan only exposes one port and needs *something* to answer HTTP
requests, so we always bind this — even when the bot itself uses long polling.
"""

from __future__ import annotations

import asyncio
import html
import logging
import time
from typing import TYPE_CHECKING, Any

from aiohttp import web

if TYPE_CHECKING:  # pragma: no cover
    from telegram.ext import Application

    from .config import Settings

logger = logging.getLogger(__name__)

SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"

_STATUS_PAGE = """<!doctype html>
<html lang="km">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin:0; min-height:100vh; display:grid; place-items:center;
        background:radial-gradient(circle at 20% 20%, #10202c, #07090c 60%);
        color:#e8f1f8; font-family: ui-sans-serif, system-ui, "Noto Sans Khmer", sans-serif; }}
  .card {{ max-width: 34rem; padding: 2rem 2.25rem; border-radius: 1.25rem;
          background: rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.12);
          box-shadow: 0 20px 60px rgba(0,0,0,.45); }}
  h1 {{ margin:0 0 .35rem; font-size: 1.6rem; }}
  .ok {{ color:#4ade80; font-weight:600; }}
  ul {{ line-height:1.7; padding-left:1.1rem; }}
  code {{ background:rgba(255,255,255,.1); padding:.1rem .35rem; border-radius:.35rem; }}
  a {{ color:#7dd3fc; }}
  .muted {{ opacity:.7; font-size:.9rem; }}
</style>
</head>
<body>
  <div class="card">
    <h1>🤖 {title}</h1>
    <p class="ok">● {status_line}</p>
    <ul>{rows}</ul>
    <p class="muted">{footer}</p>
  </div>
</body>
</html>
"""


class HttpServer:
    """Small aiohttp wrapper around health, status and webhook endpoints."""

    def __init__(
        self,
        settings: Settings,
        application: Application | None = None,
        *,
        started_at: float | None = None,
    ) -> None:
        self.settings = settings
        self.application = application
        self.started_at = started_at if started_at is not None else time.time()
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._background: set[asyncio.Task] = set()
        self._request_count = 0

    # ------------------------------------------------------------------
    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/", self.handle_index)
        app.router.add_get("/healthz", self.handle_health)
        app.router.add_get("/stats", self.handle_stats)
        if self.application is not None and self.settings.webhook_path:
            app.router.add_post(self.settings.webhook_path, self.handle_webhook)

        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.settings.host, self.settings.port)
        await self._site.start()
        logger.info(
            "HTTP server listening on %s:%s (mode=%s)",
            self.settings.host,
            self.settings.port,
            self.settings.mode,
        )

    async def stop(self) -> None:
        for task in list(self._background):
            task.cancel()
        self._background.clear()
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            self._site = None
        logger.info("HTTP server stopped")

    # ------------------------------------------------------------------
    async def handle_index(self, _request: web.Request) -> web.Response:
        self._request_count += 1
        bot_username = self._bot_username()
        rows = [
            ("Mode", self.settings.mode),
            ("Uptime", self._uptime()),
            ("Providers", ", ".join(self._provider_names()) or "none"),
        ]
        if bot_username:
            rows.append(("Telegram", f'<a href="https://t.me/{bot_username}">@{bot_username}</a>'))
        body = _STATUS_PAGE.format(
            title="VMVT.bot",
            status_line="Bot is running" if self.application else "Health server only",
            rows="".join(f"<li><b>{k}:</b> {v}</li>" for k, v in rows),
            footer=f"{html.escape(self._uptime())} • TikTok downloader without watermark",
        )
        return web.Response(text=body, content_type="text/html")

    async def handle_health(self, _request: web.Request) -> web.Response:
        self._request_count += 1
        return web.json_response(self.health_payload())

    async def handle_stats(self, _request: web.Request) -> web.Response:
        self._request_count += 1
        payload = self.health_payload()
        service = self._bot_data().get("tiktok_service") if self.application else None
        if service is not None:
            payload.update(service.stats())
        return web.json_response(payload)

    async def handle_webhook(self, request: web.Request) -> web.Response:
        """Accept an update from Telegram and hand it to PTB."""
        self._request_count += 1
        if self.application is None:  # pragma: no cover - route is not registered then
            return web.Response(status=503, text="bot not initialised")

        expected = self.settings.webhook_secret
        if expected and request.headers.get(SECRET_HEADER) != expected:
            logger.warning("Rejected webhook request with bad secret token")
            return web.Response(status=401, text="unauthorized")

        try:
            data = await request.json()
        except (ValueError, UnicodeDecodeError):
            return web.Response(status=400, text="invalid json")

        update = self._build_update(data)
        if update is None:
            return web.Response(status=400, text="invalid update")

        # Answer Telegram immediately and process in the background so slow
        # downloads never block the webhook connection.
        task = asyncio.create_task(self._process(update))
        self._background.add(task)
        task.add_done_callback(self._background.discard)
        return web.json_response({"ok": True})

    # ------------------------------------------------------------------
    def health_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": "ok",
            "mode": self.settings.mode,
            "uptime_seconds": round(time.time() - self.started_at, 1),
            "requests": self._request_count,
        }
        if self.application is None:
            payload["telegram"] = "disconnected"
        return payload

    # ------------------------------------------------------------------
    async def _process(self, update) -> None:
        try:
            await self.application.process_update(update)
        except Exception:  # pragma: no cover - defensive
            logger.exception("Error while processing webhook update")

    def _build_update(self, data: Any):
        from telegram import Update  # imported lazily to keep startup cheap

        if not isinstance(data, dict):
            return None
        try:
            return Update.de_json(data, self.application.bot)
        except Exception:  # pragma: no cover - defensive
            logger.exception("Could not parse update payload")
            return None

    def _bot_data(self) -> dict[str, Any]:
        if self.application is None:
            return {}
        data = getattr(self.application, "bot_data", None)
        return data if isinstance(data, dict) else {}

    def _bot_username(self) -> str | None:
        if self.application is None:
            return None
        bot = getattr(self.application, "bot", None)
        username = getattr(bot, "username", None)
        return username.lstrip("@") if username else None

    def _provider_names(self) -> list[str]:
        service = self._bot_data().get("tiktok_service")
        if service is None:
            return []
        return service.stats().get("providers", [])

    def _uptime(self) -> str:
        seconds = int(time.time() - self.started_at)
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours}h {minutes}m {secs}s"


async def serve_forever(settings: Settings) -> None:
    """Run only the HTTP server (used by ``python -m bot.serve``)."""
    server = HttpServer(settings)
    await server.start()
    logger.info("Health-only server ready on %s:%s", settings.host, settings.port)
    try:
        await asyncio.Event().wait()
    finally:
        await server.stop()


__all__ = ["HttpServer", "serve_forever"]
