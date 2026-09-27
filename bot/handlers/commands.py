"""Simple command handlers: /start, /help, /about, /ping, /stats."""

from __future__ import annotations

import logging
import time

from telegram import Update
from telegram.ext import ContextTypes

from .. import texts
from ..config import Settings
from ..constants import MEDIA_CACHE_KEY, SERVICE_KEY, SETTINGS_KEY, STARTED_AT_KEY
from ..utils.formatting import escape_html, human_duration

logger = logging.getLogger(__name__)


def _uptime(context: ContextTypes.DEFAULT_TYPE) -> str:
    started = context.bot_data.get(STARTED_AT_KEY, time.time())
    return human_duration(time.time() - started)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start — welcome message."""
    if update.effective_message:
        await update.effective_message.reply_text(texts.WELCOME, parse_mode="HTML")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/help — usage instructions."""
    if update.effective_message:
        await update.effective_message.reply_text(texts.HELP, parse_mode="HTML")


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/about — what this bot is."""
    if update.effective_message:
        await update.effective_message.reply_text(texts.ABOUT, parse_mode="HTML")


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/ping — quick health check from inside Telegram."""
    if not update.effective_message:
        return
    settings: Settings | None = context.bot_data.get(SETTINGS_KEY)
    mode = settings.mode if settings else "?"
    await update.effective_message.reply_text(
        f"🏓 <b>pong</b>\n"
        f"• Mode: <code>{escape_html(mode)}</code>\n"
        f"• Uptime: <code>{_uptime(context)}</code>",
        parse_mode="HTML",
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/stats — admin-only runtime statistics."""
    message = update.effective_message
    if not message:
        return

    settings: Settings | None = context.bot_data.get(SETTINGS_KEY)
    user = update.effective_user
    if not settings or not settings.is_admin(user.id if user else None):
        await message.reply_text("🚫 ពាក្យបញ្ជានេះសម្រាប់តែអ្នកគ្រប់គ្រងប៉ុណ្ណោះ។")
        return

    service = context.bot_data.get(SERVICE_KEY)
    cache = context.bot_data.get(MEDIA_CACHE_KEY)
    lines = [
        "📊 <b>ស្ថិតិ Bot</b>",
        f"• Uptime: <code>{_uptime(context)}</code>",
        f"• Mode: <code>{settings.mode}</code>",
    ]
    if service is not None:
        info = service.stats()
        providers = ", ".join(info["providers"]) or "-"
        lines.append(f"• Providers: <code>{escape_html(providers)}</code>")
        lines.append(f"• Resolve cache: <code>{info['resolve_cache']}</code>")
    if cache is not None:
        lines.append(f"• Media cache: <code>{len(cache)}</code>")

    await message.reply_text("\n".join(lines), parse_mode="HTML")


__all__ = ["about", "help_command", "ping", "start", "stats"]
