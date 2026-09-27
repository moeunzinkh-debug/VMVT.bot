"""Start only the HTTP status/health server: ``python -m bot.serve``.

Useful to keep a Render instance warm (point an uptime monitor at ``/healthz``)
or to check that the deployment works without a Telegram token.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from .config import Settings
from .http_server import serve_forever
from .logging_setup import setup_logging

logger = logging.getLogger("vmvt.serve")


def main() -> None:
    try:
        settings = Settings.from_env(require_token=False)
    except RuntimeError as exc:  # pragma: no cover - defensive
        print(f"Configuration error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    setup_logging(settings.log_level)
    logger.info("Starting health-only server on %s:%s", settings.host, settings.port)
    try:
        asyncio.run(serve_forever(settings))
    except KeyboardInterrupt:  # pragma: no cover - manual stop
        logger.info("Stopped")


if __name__ == "__main__":
    main()
