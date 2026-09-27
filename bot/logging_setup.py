"""Logging configuration."""

from __future__ import annotations

import logging
import sys

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-28s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

NOISY_LOGGERS = (
    "httpx",
    "httpcore",
    "apscheduler.executors.default",
    "apscheduler.scheduler",
    "telegram.ext.Updater",
)


def setup_logging(level: str = "INFO") -> None:
    """Configure the root logger once, at startup."""
    root = logging.getLogger()
    if root.handlers:  # already configured (e.g. under a test runner)
        root.setLevel(level)
        return

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    root.addHandler(handler)
    root.setLevel(level)

    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    logging.getLogger(__name__.split(".")[0]).setLevel(level)
