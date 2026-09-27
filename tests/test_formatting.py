"""Tests for the formatting helpers and the user-facing texts."""

from __future__ import annotations

from bot.config import TELEGRAM_MAX_CAPTION_CHARS
from bot.services.providers.base import MediaResult
from bot.texts import ABOUT, HELP, WELCOME, rate_limit_message
from bot.utils.formatting import (
    build_caption,
    clean_text,
    escape_html,
    human_bytes,
    human_duration,
    truncate,
)


def test_human_bytes() -> None:
    assert human_bytes(0) == "0 B"
    assert human_bytes(512) == "512 B"
    assert human_bytes(2048) == "2.0 KB"
    assert human_bytes(4_200_000).endswith("MB")
    assert human_bytes(3 * 1024**3).endswith("GB")
    assert human_bytes(None) == "?"


def test_human_duration() -> None:
    assert human_duration(9) == "0:09"
    assert human_duration(95) == "1:35"
    assert human_duration(3725) == "1:02:05"
    assert human_duration(None) == "?"
    assert human_duration(-5) == "?"


def test_escape_and_clean() -> None:
    assert escape_html('<script>&"x"') == "&lt;script&gt;&amp;&quot;x&quot;"
    assert escape_html(None) == ""
    assert clean_text("  a   b​ ") == "a b"
    assert truncate("អក្សរវែងៗ" * 20, 10).endswith("…")


def test_build_caption_is_html_safe_and_bounded() -> None:
    result = MediaResult(
        video_id="7123456789012345678",
        provider="tikwm",
        source_url="https://www.tiktok.com/@khmer.drama/video/7123456789012345678",
        videos=["https://cdn/a.mp4"],
        title="<b>hack</b> " + "ខ" * 2000,
        author="khmer.drama",
        duration=95,
        size=4_200_000,
        hd=True,
    )
    caption = build_caption(result, quality="🎞 HD")

    assert len(caption) <= TELEGRAM_MAX_CAPTION_CHARS
    assert "<b>hack</b>" not in caption  # user content is escaped
    assert "@khmer.drama" in caption
    assert "1:35" in caption
    assert "HD" in caption
    assert caption.startswith("🎬")


def test_build_caption_without_optional_fields() -> None:
    result = MediaResult(video_id="1", provider="tikwm", source_url="u", videos=["x"])
    caption = build_caption(result)
    assert "VMVT.bot" in caption
    assert "@" not in caption


def test_texts_are_balanced_and_khmer() -> None:
    for text in (WELCOME, HELP, ABOUT):
        assert text.count("<b>") == text.count("</b>")
        assert text.count("<code>") == text.count("</code>")
        assert "TikTok" in text
    assert "វិនាទី" in rate_limit_message(12.4)
    assert "12" in rate_limit_message(12.4)
