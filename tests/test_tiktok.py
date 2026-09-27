"""Tests for TikTok URL handling."""

from __future__ import annotations

import pytest

from bot.services import tiktok


@pytest.mark.parametrize(
    "raw,expected",
    [
        (
            "https://vm.tiktok.com/ZMhvzrfeR/",
            "https://vm.tiktok.com/ZMhvzrfeR/",
        ),
        (
            "https://vt.tiktok.com/ZSjxxxxx/?share_app_id=1233",
            "https://vt.tiktok.com/ZSjxxxxx/?share_app_id=1233",
        ),
        (
            "http://www.tiktok.com/@user/video/7123456789012345678",
            "https://www.tiktok.com/@user/video/7123456789012345678",
        ),
        (
            "www.tiktok.com/@user/video/7123456789012345678",
            "https://www.tiktok.com/@user/video/7123456789012345678",
        ),
    ],
)
def test_normalize_url(raw: str, expected: str) -> None:
    assert tiktok.normalize_url(raw) == expected


def test_extract_urls_from_chatty_message() -> None:
    text = (
        "មើលវីដេអូនេះ https://vm.tiktok.com/ZMhvzrfeR/ "
        "និង https://www.tiktok.com/@khmer.drama/video/7123456789012345678?is_copy=1 "
        "ហើយនេះ https://example.com/not-tiktok"
    )
    urls = tiktok.extract_urls(text)
    assert urls == [
        "https://vm.tiktok.com/ZMhvzrfeR/",
        "https://www.tiktok.com/@khmer.drama/video/7123456789012345678?is_copy=1",
    ]


def test_extract_urls_strips_trailing_punctuation() -> None:
    urls = tiktok.extract_urls("មកមើល៖ https://vm.tiktok.com/ZMhvzrfeR/, ល្អណាស់!")
    assert urls == ["https://vm.tiktok.com/ZMhvzrfeR/"]


def test_extract_urls_deduplicates_same_video() -> None:
    text = (
        "https://vm.tiktok.com/ZMhvzrfeR/ "
        "https://www.tiktok.com/@user/video/7123456789012345678 "
        "https://www.tiktok.com/@other/video/7123456789012345678"
    )
    assert len(tiktok.extract_urls(text)) == 2


def test_extract_urls_ignores_empty_input() -> None:
    assert tiktok.extract_urls(None) == []
    assert tiktok.extract_urls("") == []
    assert tiktok.extract_urls("គ្មានតំណទេ") == []


def test_parse_video_id_variants() -> None:
    assert tiktok.parse_video_id("https://www.tiktok.com/@u/video/7123456789012345678") == (
        "7123456789012345678"
    )
    assert tiktok.parse_video_id("https://www.tiktok.com/@u/photo/7123456789012345678") == (
        "7123456789012345678"
    )
    assert tiktok.parse_video_id("https://m.tiktok.com/v/7123456789012345678.html") == (
        "7123456789012345678"
    )
    assert tiktok.parse_video_id("https://vm.tiktok.com/ZMhvzrfeR/") == "short:ZMhvzrfeR"
    assert tiktok.parse_video_id("https://example.com/video") is None


def test_is_tiktok_url_rejects_other_hosts() -> None:
    assert tiktok.is_tiktok_url("https://vt.tiktok.com/abc/")
    assert tiktok.is_tiktok_url("vm.tiktok.com/abc/")
    assert not tiktok.is_tiktok_url("https://youtube.com/watch?v=1")
    assert not tiktok.is_tiktok_url("https://tiktok.com.evil.com/x")


def test_short_url_detection() -> None:
    assert tiktok.is_short_url("https://vm.tiktok.com/ZMhvzrfeR/")
    assert tiktok.is_short_url("https://vt.tiktok.com/ZSjxxxxx/")
    assert not tiktok.is_short_url("https://www.tiktok.com/@u/video/1234567890")


def test_author_handle() -> None:
    assert tiktok.author_handle("https://www.tiktok.com/@khmer.drama/video/7123") == "@khmer.drama"
    assert tiktok.author_handle("https://vm.tiktok.com/ZMhvzrfeR/") is None


@pytest.mark.asyncio
async def test_expand_short_url_returns_canonical_url() -> None:
    class Session:
        def get(self, url, **kwargs):
            class Resp:
                url = "https://www.tiktok.com/@khmer.drama/video/7123456789012345678"

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    return False

            return Resp()

    expanded = await tiktok.expand_short_url("https://vm.tiktok.com/ZMhvzrfeR/", Session())
    assert expanded == "https://www.tiktok.com/@khmer.drama/video/7123456789012345678"


@pytest.mark.asyncio
async def test_expand_short_url_returns_none_on_failure() -> None:
    class Session:
        def get(self, url, **kwargs):
            raise OSError("blocked")

    assert await tiktok.expand_short_url("https://vm.tiktok.com/ZMhvzrfeR/", Session()) is None
