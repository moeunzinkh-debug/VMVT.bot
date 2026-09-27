"""Keys used inside ``bot_data`` plus the bot command menu."""

from __future__ import annotations

from telegram import BotCommand

SETTINGS_KEY = "settings"
SERVICE_KEY = "tiktok_service"
MEDIA_CACHE_KEY = "media_cache"
RATE_LIMITER_KEY = "rate_limiter"
STARTED_AT_KEY = "started_at"

COMMANDS: tuple[BotCommand, ...] = (
    BotCommand("start", "ចាប់ផ្តើម / Start"),
    BotCommand("help", "របៀបប្រើប្រាស់ / Help"),
    BotCommand("about", "អំពី Bot / About"),
    BotCommand("ping", "ពិនិត្យស្ថានភាព / Ping"),
)
