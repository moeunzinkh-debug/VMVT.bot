"""Smoke tests for the application factory (no network calls)."""

from __future__ import annotations

import pytest
from telegram.ext import CommandHandler, MessageHandler

from bot.app import build_application, debug_state
from bot.constants import SETTINGS_KEY


def test_application_registers_handlers(settings) -> None:
    application = build_application(settings)

    handlers = application.handlers[0]
    commands = {
        command for h in handlers if isinstance(h, CommandHandler) for command in h.commands
    }
    assert commands == {"start", "help", "about", "ping", "stats"}

    message_handlers = [h for h in handlers if isinstance(h, MessageHandler)]
    assert len(message_handlers) == 1

    assert application.bot_data[SETTINGS_KEY] is settings
    assert debug_state(application)["handlers"] == 6


def test_application_uses_the_configured_token(settings) -> None:
    application = build_application(settings)
    assert application.bot.token == settings.bot_token


def test_settings_are_reachable_from_bot_data(settings) -> None:
    application = build_application(settings)
    assert application.bot_data[SETTINGS_KEY].max_upload_bytes == settings.max_upload_bytes


@pytest.mark.asyncio
async def test_bootstrap_and_teardown_start_the_http_server(settings) -> None:
    from bot.app import bootstrap, teardown
    from bot.http_server import HttpServer

    application = build_application(settings)
    settings = settings.__class__(**{**settings.__dict__, "port": 0, "host": "127.0.0.1"})
    application.bot_data[SETTINGS_KEY] = settings

    await bootstrap(application)
    try:
        assert isinstance(application.bot_data["http_server"], HttpServer)
        assert "tikwm" in application.bot_data["tiktok_service"].stats()["providers"]
        assert application.bot_data["media_cache"] is not None
        assert application.bot_data["rate_limiter"] is not None
    finally:
        await teardown(application)

    assert "http_server" not in application.bot_data
    assert "aiohttp_session" not in application.bot_data
