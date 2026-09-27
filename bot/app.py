"""Application factory: builds the PTB application and its runtime wiring."""

from __future__ import annotations

import logging
import time
from typing import Any

import aiohttp
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from . import texts
from .config import Settings
from .constants import (
    COMMANDS,
    MEDIA_CACHE_KEY,
    RATE_LIMITER_KEY,
    SERVICE_KEY,
    SETTINGS_KEY,
    STARTED_AT_KEY,
)
from .handlers import about, handle_message, help_command, ping, start, stats
from .http_server import HttpServer
from .services import MediaCache, RateLimiter, TikTokService

logger = logging.getLogger(__name__)

HTTP_SERVER_KEY = "http_server"
AIOHTTP_SESSION_KEY = "aiohttp_session"


def build_application(settings: Settings) -> Application:
    """Create the bot application with every handler registered."""
    request = HTTPXRequest(
        connection_pool_size=16,
        connect_timeout=20.0,
        read_timeout=30.0,
        write_timeout=120.0,
        pool_timeout=5.0,
        media_write_timeout=600.0,
    )
    get_updates_request = HTTPXRequest(
        connection_pool_size=2,
        connect_timeout=20.0,
        read_timeout=45.0,  # long polling needs a generous read timeout
        pool_timeout=5.0,
    )

    application = (
        ApplicationBuilder()
        .token(settings.bot_token)
        .request(request)
        .get_updates_request(get_updates_request)
        .post_init(_post_init)
        .post_stop(_post_stop)
        .build()
    )
    application.bot_data[SETTINGS_KEY] = settings
    application.bot_data[STARTED_AT_KEY] = time.time()

    _register_handlers(application)
    application.add_error_handler(_error_handler)
    return application


def _register_handlers(application: Application) -> None:
    for command, callback in (
        ("start", start),
        ("help", help_command),
        ("about", about),
        ("ping", ping),
        ("stats", stats),
    ):
        application.add_handler(CommandHandler(command, callback))

    # Any message (text or caption) that is not a command goes to the link worker.
    application.add_handler(
        MessageHandler((filters.TEXT | filters.CAPTION) & ~filters.COMMAND, handle_message)
    )


# ----------------------------------------------------------------------
async def _post_init(application: Application) -> None:
    """Create the aiohttp session, caches and the HTTP server."""
    await bootstrap(application)
    try:
        await application.bot.set_my_commands(COMMANDS)
    except Exception:  # pragma: no cover - never fatal
        logger.debug("Could not register the command menu", exc_info=True)


async def _post_stop(application: Application) -> None:
    await teardown(application)


async def bootstrap(application: Application) -> None:
    """Start everything that needs a running event loop."""
    settings: Settings = application.bot_data[SETTINGS_KEY]

    timeout = aiohttp.ClientTimeout(
        total=None, sock_connect=settings.connect_timeout_s, sock_read=120
    )
    session = aiohttp.ClientSession(timeout=timeout)
    application.bot_data[AIOHTTP_SESSION_KEY] = session

    application.bot_data[SERVICE_KEY] = TikTokService(settings, session)
    application.bot_data[MEDIA_CACHE_KEY] = MediaCache(
        ttl=settings.media_cache_ttl, max_size=settings.media_cache_size
    )
    application.bot_data[RATE_LIMITER_KEY] = RateLimiter(settings.rate_limit_per_min)

    server = HttpServer(settings, application, started_at=application.bot_data[STARTED_AT_KEY])
    await server.start()
    application.bot_data[HTTP_SERVER_KEY] = server

    logger.info(
        "VMVT.bot started (mode=%s, providers=%s, max_upload=%dMB)",
        settings.mode,
        application.bot_data[SERVICE_KEY].stats()["providers"],
        settings.max_upload_mb,
    )


async def teardown(application: Application) -> None:
    """Close the HTTP server and the aiohttp session."""
    server: HttpServer | None = application.bot_data.get(HTTP_SERVER_KEY)
    if server is not None:
        await server.stop()
        application.bot_data.pop(HTTP_SERVER_KEY, None)

    session = application.bot_data.get(AIOHTTP_SESSION_KEY)
    if session is not None:
        await session.close()
        application.bot_data.pop(AIOHTTP_SESSION_KEY, None)


# ----------------------------------------------------------------------
async def _error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log unhandled errors and tell the user something went wrong."""
    error = getattr(context, "error", None)
    logger.exception("Unhandled error while processing update", exc_info=error)

    message = getattr(update, "effective_message", None) if update else None
    if message is None:
        return
    try:
        await message.reply_text(texts.ERR_GENERIC)
    except Exception:  # pragma: no cover - best effort
        logger.debug("Could not notify the user about the error", exc_info=True)


def debug_state(application: Application) -> dict[str, Any]:
    """Small helper used by tests and debugging sessions."""
    return {
        "handlers": len(application.handlers[0]) if application.handlers else 0,
        "bot_data_keys": sorted(application.bot_data),
        "updates": len(Update.ALL_TYPES),
    }
