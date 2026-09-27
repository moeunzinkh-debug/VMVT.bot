"""Tests for environment based configuration."""

from __future__ import annotations

import pytest

from bot.config import Settings


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in (
        "BOT_TOKEN",
        "TELEGRAM_BOT_TOKEN",
        "WEBHOOK_URL",
        "PUBLIC_URL",
        "RENDER_EXTERNAL_URL",
        "USE_WEBHOOK",
        "MODE",
        "PORT",
        "ADMIN_IDS",
        "MAX_UPLOAD_MB",
        "TIKWM_ENABLED",
        "RATE_LIMIT_PER_MIN",
    ):
        monkeypatch.delenv(key, raising=False)


def test_token_is_required(monkeypatch) -> None:
    with pytest.raises(RuntimeError, match="BOT_TOKEN"):
        Settings.from_env()

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1:abc")
    assert Settings.from_env().bot_token == "1:abc"


def test_polling_is_the_default(monkeypatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "1:abc")
    settings = Settings.from_env()
    assert settings.mode == "polling"
    assert settings.use_webhook is False
    assert settings.port == 8080


def test_webhook_mode_derives_url_from_render(monkeypatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "1:abc")
    monkeypatch.setenv("USE_WEBHOOK", "true")
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://vmvt-bot.onrender.com/")

    settings = Settings.from_env()
    assert settings.mode == "webhook"
    assert settings.use_webhook is True
    assert settings.webhook_endpoint() == "https://vmvt-bot.onrender.com/webhook"


def test_explicit_webhook_url_wins(monkeypatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "1:abc")
    monkeypatch.setenv("WEBHOOK_URL", "https://bot.example.com")
    monkeypatch.setenv("WEBHOOK_PATH", "/tg-updates")
    settings = Settings.from_env()
    assert settings.mode == "polling"  # needs USE_WEBHOOK or MODE=webhook
    assert settings.webhook_endpoint() == "https://bot.example.com/tg-updates"

    monkeypatch.setenv("MODE", "webhook")
    assert Settings.from_env().mode == "webhook"


def test_numeric_and_boolean_env_parsing(monkeypatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "1:abc")
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setenv("MAX_UPLOAD_MB", "40")
    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "not-a-number")
    monkeypatch.setenv("TIKWM_ENABLED", "off")
    monkeypatch.setenv("ADMIN_IDS", "111, 222,not-an-id,-333")

    settings = Settings.from_env()
    assert settings.port == 10000
    assert settings.max_upload_bytes == 40 * 1024 * 1024
    assert settings.rate_limit_per_min == 8  # invalid values fall back to the default
    assert settings.tikwm_enabled is False
    assert settings.admin_ids == (111, 222, -333)


def test_admin_detection(monkeypatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "1:abc")
    monkeypatch.setenv("ADMIN_IDS", "555")
    settings = Settings.from_env()
    assert settings.is_admin(555)
    assert not settings.is_admin(556)
    assert not settings.is_admin(None)


def test_invalid_mode_falls_back_to_auto(monkeypatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "1:abc")
    monkeypatch.setenv("MODE", "spaceship")
    assert Settings.from_env().mode == "polling"


def test_serve_mode_does_not_require_a_token() -> None:
    settings = Settings.from_env(require_token=False)
    assert settings.bot_token == ""
