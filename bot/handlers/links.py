"""The heart of the bot: turn a TikTok link into a watermark-free video."""

from __future__ import annotations

import contextlib
import logging
from typing import Any

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Update,
)
from telegram.constants import ChatType, ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from .. import texts
from ..config import TELEGRAM_MAX_PHOTO_BYTES, Settings
from ..constants import MEDIA_CACHE_KEY, RATE_LIMITER_KEY, SERVICE_KEY, SETTINGS_KEY
from ..services import (
    DownloadError,
    MediaResult,
    MediaTooLargeError,
    RateLimiter,
    ResolveError,
    TikTokService,
)
from ..services import cache as cache_module
from ..services import tiktok as tiktok_links
from ..utils.formatting import build_caption

logger = logging.getLogger(__name__)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle any text message that may contain TikTok links."""
    message = update.effective_message
    if message is None:
        return

    settings: Settings | None = context.bot_data.get(SETTINGS_KEY)
    service: TikTokService | None = context.bot_data.get(SERVICE_KEY)
    limiter: RateLimiter | None = context.bot_data.get(RATE_LIMITER_KEY)
    if settings is None or service is None:  # pragma: no cover - bootstrap guarantees this
        logger.error("Bot data is not initialised")
        return

    text = " ".join(part for part in (message.text, message.caption) if part)
    urls = tiktok_links.extract_urls(text)
    if not urls:
        if update.effective_chat and update.effective_chat.type == ChatType.PRIVATE:
            await message.reply_text(texts.NO_LINK_HINT, parse_mode=ParseMode.HTML)
        return

    user = update.effective_user
    if limiter is not None and not settings.is_admin(user.id if user else None):
        wait_for = limiter.check(user.id if user else 0)
        if wait_for:
            await message.reply_text(texts.rate_limit_message(wait_for), parse_mode=ParseMode.HTML)
            return

    # A single message may contain several links; answer them in order.
    for url in urls[: settings.max_links_per_message]:
        await _process_link(update, context, settings, service, url)


# ----------------------------------------------------------------------
async def _process_link(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    settings: Settings,
    service: TikTokService,
    url: str,
) -> None:
    message = update.effective_message
    if message is None:  # pragma: no cover - guarded by caller
        return

    status = await message.reply_text(texts.STATUS_RESOLVING)
    try:
        try:
            result = await service.resolve(url)
        except ResolveError as exc:
            logger.info("Could not resolve %s: %s", url, exc)
            await _edit(
                status,
                texts.ERR_PROVIDERS_DOWN if exc.retryable else texts.ERR_NOT_FOUND,
            )
            return

        cache_key = result.video_id or tiktok_links.parse_video_id(url) or url
        media_cache: cache_module.MediaCache | None = context.bot_data.get(MEDIA_CACHE_KEY)

        cached = media_cache.get(cache_key) if media_cache else None
        if cached is not None and cached.kind == "video":
            logger.debug("Reusing cached Telegram file_id for %s", cache_key)
            await _delete(status)
            await message.reply_video(
                video=cached.file_id,
                caption=build_caption(result, quality="🎞 HD" if result.hd else None),
                parse_mode=ParseMode.HTML,
                reply_markup=_keyboard(result),
            )
            return

        if result.is_slideshow:
            await _edit(status, texts.STATUS_DOWNLOADING)
            delivered = await _send_slideshow(message, context, settings, service, result)
        else:
            delivered = await _send_video(message, settings, service, result, status)

        if delivered and delivered[0] is not None and media_cache is not None:
            media_cache.remember_video(cache_key, delivered[0])
    except TelegramError as exc:
        logger.warning("Telegram error while handling %s: %s", url, exc)
        await _edit(status, texts.ERR_UPLOAD_FAILED)
        return
    finally:
        await _delete(status)


# ----------------------------------------------------------------------
async def _send_video(
    message: Any,
    settings: Settings,
    service: TikTokService,
    result: MediaResult,
    status: Any,
) -> tuple[str | None, bool]:
    """Download and upload the video. Returns ``(file_id, too_large)``."""
    candidates = result.video_candidates(limit=3)
    if not candidates:
        await _edit(status, texts.ERR_EMPTY_MEDIA)
        return (None, False)

    caption = build_caption(result, quality="🎞 HD" if result.hd else None)
    keyboard = _keyboard(result)
    too_large = False

    for candidate in candidates:
        try:
            await _edit(status, texts.STATUS_DOWNLOADING)
            downloaded = await service.download(
                candidate, max_bytes=settings.max_upload_bytes, suffix=".mp4"
            )
        except MediaTooLargeError as exc:
            logger.info("Media too large (%s bytes): %s", exc.size, candidate)
            too_large = True
            continue
        except DownloadError as exc:
            logger.info("Download failed for %s: %s", candidate, exc)
            continue

        try:
            await _edit(status, texts.STATUS_UPLOADING)
            with downloaded.path.open("rb") as handle:
                sent = await message.reply_video(
                    video=handle,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                    supports_streaming=True,
                    duration=result.duration,
                    width=result.width,
                    height=result.height,
                    filename=_filename(result),
                    write_timeout=600,
                    read_timeout=120,
                )
            return (sent.video.file_id, False)
        except TelegramError as exc:
            logger.warning("Upload failed for %s: %s", candidate, exc)
        finally:
            downloaded.cleanup()

    return await _send_by_url(message, result, caption, keyboard, status, too_large)


async def _send_by_url(
    message: Any,
    result: MediaResult,
    caption: str,
    keyboard: InlineKeyboardMarkup,
    status: Any,
    too_large: bool,
) -> tuple[str | None, bool]:
    """Last resort: let Telegram fetch the file, or share the direct link."""
    best = result.best_video
    if not best:
        await _edit(status, texts.ERR_EMPTY_MEDIA)
        return (None, too_large)

    if too_large:
        await _edit(status, texts.ERR_TOO_LARGE)

    try:
        sent = await message.reply_video(
            video=best,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            supports_streaming=True,
            duration=result.duration,
            write_timeout=300,
        )
        return (sent.video.file_id, too_large)
    except TelegramError as exc:
        logger.warning("Direct URL upload failed for %s: %s", best, exc)

    await message.reply_text(
        texts.FALLBACK_LINK_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(texts.DOWNLOAD_BUTTON, url=best)]]
        ),
    )
    return (None, too_large)


async def _send_slideshow(
    message: Any,
    context: ContextTypes.DEFAULT_TYPE,
    settings: Settings,
    service: TikTokService,
    result: MediaResult,
) -> tuple[str | None, bool]:
    """Send an image post (slideshow) as a Telegram media group."""
    urls = result.images[: settings.max_slideshow_images]
    if not urls:
        await message.reply_text(texts.ERR_EMPTY_MEDIA)
        return (None, False)

    media: list[InputMediaPhoto] = []
    handles: list[Any] = []
    files: list[Any] = []
    caption = texts.slideshow_caption(result, len(urls))

    try:
        for index, url in enumerate(urls):
            try:
                downloaded = await service.download(
                    url, max_bytes=TELEGRAM_MAX_PHOTO_BYTES, suffix=".jpg"
                )
            except DownloadError as exc:
                logger.info("Slideshow image failed (%s): %s", url, exc)
                continue
            files.append(downloaded)
            handle = downloaded.path.open("rb")
            handles.append(handle)
            media.append(
                InputMediaPhoto(
                    media=handle,
                    caption=caption if index == 0 else None,
                    parse_mode=ParseMode.HTML if index == 0 else None,
                )
            )

        if not media:
            await message.reply_text(texts.ERR_EMPTY_MEDIA)
            return (None, False)

        sent_messages = await message.reply_media_group(media=media, write_timeout=600)
        first = sent_messages[0] if sent_messages else None
        file_id = getattr(getattr(first, "photo", None), "file_id", None) if first else None
        return (file_id, False)
    except TelegramError as exc:
        logger.warning("Slideshow upload failed: %s", exc)
        await message.reply_text(texts.ERR_UPLOAD_FAILED)
        return (None, False)
    finally:
        for handle in handles:
            with contextlib.suppress(OSError):  # pragma: no cover - best effort
                handle.close()
        for downloaded in files:
            downloaded.cleanup()


# ----------------------------------------------------------------------
def _keyboard(result: MediaResult) -> InlineKeyboardMarkup:
    """Inline buttons under every delivered video."""
    buttons: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []

    if result.source_url:
        row.append(InlineKeyboardButton(texts.ORIGINAL_BUTTON, url=result.source_url))
    profile = result.profile_url
    if profile:
        row.append(InlineKeyboardButton(texts.AUTHOR_BUTTON, url=profile))
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def _filename(result: MediaResult) -> str:
    author = (result.author or "tiktok").lstrip("@") or "tiktok"
    video_id = result.video_id or "video"
    safe_author = "".join(ch for ch in author if ch.isalnum() or ch in "._-")[:24] or "tiktok"
    return f"{safe_author}_{video_id}.mp4"


async def _edit(message: Any, text: str) -> None:
    """Best-effort edit of the progress message (HTML enabled)."""
    try:
        await message.edit_text(text, parse_mode=ParseMode.HTML)
    except TelegramError as exc:  # message unchanged / already gone / too old
        logger.debug("Could not edit status message: %s", exc)


async def _delete(message: Any) -> None:
    """Remove the progress message once the real media is on its way."""
    try:
        await message.delete()
    except TelegramError as exc:  # pragma: no cover - missing rights in groups
        logger.debug("Could not delete status message: %s", exc)


__all__ = ["handle_message"]
