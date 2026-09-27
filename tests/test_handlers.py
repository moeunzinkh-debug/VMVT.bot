"""End-to-end-ish tests for the link handler (Telegram side is mocked)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.constants import ChatType
from telegram.error import TelegramError

from bot.constants import (
    MEDIA_CACHE_KEY,
    RATE_LIMITER_KEY,
    SERVICE_KEY,
    SETTINGS_KEY,
)
from bot.handlers.links import _filename, _keyboard, handle_message
from bot.services import (
    DownloadError,
    MediaTooLargeError,
    ResolveError,
)
from bot.services.cache import MediaCache
from bot.services.downloader import DownloadedFile
from bot.services.providers import MediaResult
from bot.services.rate_limit import RateLimiter


def make_context(settings, service, cache=None, limiter=None) -> MagicMock:
    context = MagicMock()
    context.bot_data = {
        SETTINGS_KEY: settings,
        SERVICE_KEY: service,
        MEDIA_CACHE_KEY: cache if cache is not None else MediaCache(ttl=60, max_size=10),
        RATE_LIMITER_KEY: limiter if limiter is not None else RateLimiter(max_events=10),
    }
    return context


def make_update(text: str, chat_type: str = ChatType.PRIVATE, user_id: int = 42) -> tuple:
    status = MagicMock()
    status.edit_text = AsyncMock()
    status.delete = AsyncMock()

    sent = MagicMock()
    sent.video.file_id = "TELEGRAM_FILE_ID"

    message = MagicMock()
    message.text = text
    message.caption = None
    message.reply_text = AsyncMock(return_value=status)
    message.reply_video = AsyncMock(return_value=sent)
    message.reply_media_group = AsyncMock(return_value=[sent])

    update = MagicMock()
    update.effective_message = message
    update.effective_chat = MagicMock(type=chat_type)
    update.effective_user = MagicMock(id=user_id)
    return update, message, status


def fake_download(tmp_path: Path, content: bytes = b"video-bytes") -> DownloadedFile:
    path = tmp_path / "clip.mp4"
    path.write_bytes(content)
    return DownloadedFile(path=path, size=len(content), content_type="video/mp4", url="u")


@pytest.mark.asyncio
async def test_happy_path_uploads_video_and_caches_file_id(
    settings, tmp_path, video_result
) -> None:
    # Unknown size skips the fast path and exercises local download/upload.
    video_result.size = None
    service = MagicMock()
    service.resolve = AsyncMock(return_value=video_result)
    service.download = AsyncMock(return_value=fake_download(tmp_path))
    cache = MediaCache(ttl=60, max_size=10)
    update, message, status = make_update("មើលនេះ https://vm.tiktok.com/ZMhvzrfeR/ ល្អណាស់")

    await handle_message(update, make_context(settings, service, cache))

    message.reply_video.assert_awaited_once()
    kwargs = message.reply_video.await_args.kwargs
    assert kwargs["parse_mode"] == "HTML"
    assert kwargs["supports_streaming"] is True
    assert kwargs["duration"] == video_result.duration
    assert kwargs["filename"].endswith(".mp4")
    assert "@khmer.drama" in kwargs["caption"]
    assert cache.get(video_result.video_id).file_id == "TELEGRAM_FILE_ID"
    status.delete.assert_awaited()


@pytest.mark.asyncio
async def test_small_video_uses_fast_telegram_url_delivery(settings, video_result) -> None:
    service = MagicMock()
    service.resolve = AsyncMock(return_value=video_result)
    service.download = AsyncMock(side_effect=AssertionError("fast path should avoid download"))

    update, message, _ = make_update("https://vm.tiktok.com/ZMhvzrfeR/")
    await handle_message(update, make_context(settings, service))

    message.reply_video.assert_awaited_once()
    assert message.reply_video.await_args.kwargs["video"] == video_result.best_video
    service.download.assert_not_awaited()


@pytest.mark.asyncio
async def test_cached_file_id_is_reused_without_redownload(settings, video_result) -> None:
    cache = MediaCache(ttl=60, max_size=10)
    cache.remember_video(video_result.video_id, "CACHED_FILE_ID")

    service = MagicMock()
    service.resolve = AsyncMock(return_value=video_result)
    service.download = AsyncMock(side_effect=AssertionError("should not download"))

    update, message, _ = make_update("https://www.tiktok.com/@a/video/7123456789012345678")
    await handle_message(update, make_context(settings, service, cache))

    message.reply_video.assert_awaited_once()
    assert message.reply_video.await_args.kwargs["video"] == "CACHED_FILE_ID"


@pytest.mark.asyncio
async def test_rate_limited_user_gets_a_polite_message(settings, video_result) -> None:
    limiter = RateLimiter(max_events=1, period=60)
    limiter.check(42)  # consume the single allowance for user 42

    service = MagicMock()
    service.resolve = AsyncMock(return_value=video_result)
    service.download = AsyncMock(side_effect=AssertionError("should not download"))

    update, message, _ = make_update("https://vm.tiktok.com/ZMhvzrfeR/")
    await handle_message(update, make_context(settings, service, limiter=limiter))

    service.resolve.assert_not_awaited()
    body = message.reply_text.await_args.args[0]
    assert "សូមបន្ថយល្បឿន" in body


@pytest.mark.asyncio
async def test_message_without_link_only_answers_in_private_chat(settings, video_result) -> None:
    service = MagicMock()

    update, message, _ = make_update("សួស្តី!", chat_type=ChatType.GROUP)
    await handle_message(update, make_context(settings, service))
    message.reply_text.assert_not_awaited()

    update, message, _ = make_update("សួស្តី!", chat_type=ChatType.PRIVATE)
    await handle_message(update, make_context(settings, service))
    message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_failure_shows_helpful_error(settings) -> None:
    service = MagicMock()
    service.resolve = AsyncMock(side_effect=ResolveError("providers down", retryable=False))
    update, _, status = make_update("https://vm.tiktok.com/ZMhvzrfeR/")

    await handle_message(update, make_context(settings, service))

    text = status.edit_text.await_args.args[0]
    assert "រកមិនឃើញ" in text


@pytest.mark.asyncio
async def test_oversized_video_reports_limit_without_external_link(settings, video_result) -> None:
    video_result.size = 90_000_000
    service = MagicMock()
    service.resolve = AsyncMock(return_value=video_result)
    service.download = AsyncMock(side_effect=MediaTooLargeError("too big", 90_000_000))
    service.download_with_ytdlp = AsyncMock(side_effect=DownloadError("too big"))

    update, message, status = make_update("https://vm.tiktok.com/ZMhvzrfeR/")
    context = make_context(settings, service)

    # Telegram refuses both uploads; the bot reports the limit instead of
    # sending an external download link.
    message.reply_video = AsyncMock(side_effect=TelegramError("file too large"))

    await handle_message(update, context)

    message.reply_video.assert_awaited_once()
    assert message.reply_video.await_args.kwargs["video"] == video_result.best_video
    final_reply = message.reply_text.await_args
    assert "reply_markup" not in final_reply.kwargs
    assert "ធំពេក" in final_reply.args[0]
    status.delete.assert_awaited()


@pytest.mark.asyncio
async def test_slideshow_is_sent_as_media_group(settings, tmp_path) -> None:
    slideshow = MediaResult(
        video_id="7999999999999999999",
        provider="tikwm",
        source_url="https://www.tiktok.com/@u/photo/7999999999999999999",
        images=["https://cdn/1.jpg", "https://cdn/2.jpg"],
        title="រូបភាព",
        author="photo.user",
    )
    service = MagicMock()
    service.resolve = AsyncMock(return_value=slideshow)

    def _download(url, **kwargs):
        path = tmp_path / f"{url.rsplit('/', 1)[-1]}"
        path.write_bytes(b"image-bytes")
        return DownloadedFile(path=path, size=11, content_type="image/jpeg", url=url)

    service.download = AsyncMock(side_effect=_download)
    update, message, _ = make_update("https://www.tiktok.com/@u/photo/7999999999999999999")

    await handle_message(update, make_context(settings, service))

    media = message.reply_media_group.await_args.kwargs["media"]
    assert len(media) == 2
    assert media[0].caption is not None
    assert media[1].caption is None


@pytest.mark.asyncio
async def test_download_failure_reports_error(settings, video_result) -> None:
    video_result.size = None
    service = MagicMock()
    service.resolve = AsyncMock(return_value=video_result)
    service.download = AsyncMock(side_effect=DownloadError("network down"))
    service.download_with_ytdlp = AsyncMock(side_effect=DownloadError("extractor down"))
    message_sent = MagicMock()
    message_sent.video.file_id = "X"

    update, message, _ = make_update("https://vm.tiktok.com/ZMhvzrfeR/")
    message.reply_video = AsyncMock(return_value=message_sent)

    await handle_message(update, make_context(settings, service))

    # falls back to sending the URL directly
    assert message.reply_video.await_args.kwargs["video"] == video_result.best_video


@pytest.mark.asyncio
async def test_ytdlp_fallback_uploads_video_into_chat(settings, tmp_path, video_result) -> None:
    video_result.size = None
    service = MagicMock()
    service.resolve = AsyncMock(return_value=video_result)
    service.download = AsyncMock(side_effect=DownloadError("expired CDN URL"))
    local_video = fake_download(tmp_path, b"recovered-video")
    service.download_with_ytdlp = AsyncMock(return_value=local_video)

    update, message, _ = make_update("https://vm.tiktok.com/ZMhvzrfeR/")
    await handle_message(update, make_context(settings, service))

    service.download_with_ytdlp.assert_awaited_once_with(
        video_result.source_url, max_bytes=settings.max_upload_bytes
    )
    message.reply_video.assert_awaited_once()
    assert message.reply_video.await_args.kwargs["filename"].endswith(".mp4")
    assert not local_video.path.exists()
    # No message containing an external download button is sent.
    assert all("reply_markup" not in call.kwargs for call in message.reply_text.await_args_list[1:])


def test_keyboard_and_filename(video_result) -> None:
    markup = _keyboard(video_result)
    buttons = markup.inline_keyboard[0]
    assert len(buttons) == 2
    assert buttons[0].url == video_result.source_url
    assert buttons[1].url == "https://www.tiktok.com/@khmer.drama"
    assert _filename(video_result) == "khmer.drama_7123456789012345678.mp4"


def test_keyboard_without_author() -> None:
    result = MediaResult(video_id="1", provider="t", source_url="", videos=["x"])
    assert list(_keyboard(result).inline_keyboard) == []
    assert _filename(result) == "tiktok_1.mp4"
