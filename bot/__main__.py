"""Entry point: ``python -m bot`` (Render runs this through the Procfile)."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
import sys

from telegram import Update

from .app import bootstrap, build_application, teardown
from .config import Settings
from .logging_setup import setup_logging

logger = logging.getLogger("vmvt")


def main() -> None:
    try:
        settings = Settings.from_env()
    except RuntimeError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    setup_logging(settings.log_level)
    application = build_application(settings)

    if settings.use_webhook:
        try:
            asyncio.run(_run_webhook(application, settings))
        except KeyboardInterrupt:  # pragma: no cover - manual stop
            logger.info("Shutting down (interrupted)")
    else:
        logger.info("Starting in long-polling mode")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=settings.drop_pending_updates,
            # A Render instance can take a while to come up; retry instead of
            # exiting on the first network hiccup.
            bootstrap_retries=5,
        )


async def _run_webhook(application, settings: Settings) -> None:
    """Run with a webhook (the HTTP server in :mod:`bot.http_server` owns the port)."""
    if not settings.webhook_url:
        raise RuntimeError(
            "USE_WEBHOOK is enabled but no public URL is configured. "
            "Set WEBHOOK_URL (or PUBLIC_URL / RENDER_EXTERNAL_URL)."
        )

    await application.initialize()
    await bootstrap(application)
    await application.start()

    url = settings.webhook_endpoint()
    await application.bot.set_webhook(
        url=url,
        allowed_updates=Update.ALL_TYPES,
        secret_token=settings.webhook_secret,
        drop_pending_updates=settings.drop_pending_updates,
    )
    logger.info("Webhook registered at %s", url)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError, RuntimeError):
            loop.add_signal_handler(sig, stop_event.set)

    try:
        await stop_event.wait()
    finally:
        logger.info("Shutting down webhook mode")
        with contextlib.suppress(Exception):
            await application.bot.delete_webhook()
        await application.stop()
        await teardown(application)
        await application.shutdown()


if __name__ == "__main__":
    main()
