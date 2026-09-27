"""Tests for the download providers."""

from __future__ import annotations

import pytest
from conftest import FakeResponse, FakeSession

from bot.services.providers import MediaResult, ProviderError, TikWMProvider, YtDlpProvider

TIKWM_VIDEO_PAYLOAD = {
    "code": 0,
    "msg": "success",
    "data": {
        "id": "7123456789012345678",
        "title": "រឿងខ្លី ភាគ ១ #drama",
        "duration": 42,
        "cover": "https://p16-sign.tiktokcdn.com/cover.jpeg",
        "origin_cover": "/origin.jpeg",
        "ai_dynamic_cover": "https://p16-sign.tiktokcdn.com/dyn.jpeg",
        "play": "https://v16-webapp.tiktokcdn.com/video.mp4",
        "wmplay": "https://v16-webapp.tiktokcdn.com/video-wm.mp4",
        "hdplay": "https://v16-webapp.tiktokcdn.com/video-hd.mp4",
        "size": 3145728,
        "music": "https://sf16.tiktokcdn.com/music.mp3",
        "music_info": {"title": "បទភ្លេង", "author": "artist"},
        "author": {"id": "123", "unique_id": "khmer.drama", "nickname": "Drama KH"},
    },
}

TIKWM_SLIDESHOW_PAYLOAD = {
    "code": 0,
    "data": {
        "id": "7999999999999999999",
        "title": "រូបភាពស្អាត",
        "duration": 0,
        "images": ["/media/img1.jpeg", "https://p16.tiktokcdn.com/img2.jpeg"],
        "author": {"unique_id": "photo.user"},
    },
}


@pytest.mark.asyncio
async def test_tikwm_prefers_hd_then_nowm_then_wm() -> None:
    session = FakeSession(FakeResponse(TIKWM_VIDEO_PAYLOAD))
    result = await TikWMProvider(session).fetch("https://vm.tiktok.com/ZMhvzrfeR/")

    assert result.provider == "tikwm"
    assert result.hd is True
    assert result.video_id == "7123456789012345678"
    assert result.videos == [
        "https://v16-webapp.tiktokcdn.com/video-hd.mp4",
        "https://v16-webapp.tiktokcdn.com/video.mp4",
        "https://v16-webapp.tiktokcdn.com/video-wm.mp4",
    ]
    assert result.author == "khmer.drama"
    assert result.author_handle == "@khmer.drama"
    assert result.duration == 42
    assert result.size == 3145728
    assert result.music == "បទភ្លេង"
    assert not result.is_slideshow
    assert result.video_candidates(limit=2) == result.videos[:2]


def test_tikwm_makes_root_relative_urls_absolute() -> None:
    session = FakeSession(FakeResponse(TIKWM_SLIDESHOW_PAYLOAD))
    provider = TikWMProvider(session)
    assert provider._absolute("/media/img1.jpeg") == "https://www.tikwm.com/media/img1.jpeg"
    assert provider._absolute("//cdn.example.com/a.mp4") == "https://cdn.example.com/a.mp4"
    assert provider._absolute("javascript:void(0)") == ""
    assert provider._absolute(None) == ""


@pytest.mark.asyncio
async def test_tikwm_parses_slideshows() -> None:
    session = FakeSession(FakeResponse(TIKWM_SLIDESHOW_PAYLOAD))
    result = await TikWMProvider(session).fetch(
        "https://www.tiktok.com/@u/photo/7999999999999999999"
    )

    assert result.is_slideshow
    assert result.images == [
        "https://www.tikwm.com/media/img1.jpeg",
        "https://p16.tiktokcdn.com/img2.jpeg",
    ]
    assert result.best_video is None


@pytest.mark.asyncio
async def test_tikwm_raises_on_error_code() -> None:
    session = FakeSession(FakeResponse({"code": -1, "msg": "Free Api Limit", "data": None}))
    with pytest.raises(ProviderError) as excinfo:
        await TikWMProvider(session).fetch("https://vm.tiktok.com/ZMhvzrfeR/")
    assert "Free Api Limit" in str(excinfo.value)
    assert excinfo.value.retryable is True


@pytest.mark.asyncio
async def test_tikwm_raises_on_server_error() -> None:
    session = FakeSession(FakeResponse({}, status=503))
    with pytest.raises(ProviderError) as excinfo:
        await TikWMProvider(session).fetch("https://vm.tiktok.com/ZMhvzrfeR/")
    assert "503" in str(excinfo.value)


@pytest.mark.asyncio
async def test_tikwm_raises_when_no_media_returned() -> None:
    payload = {"code": 0, "data": {"id": "1", "title": "x", "play": "", "hdplay": None}}
    session = FakeSession(FakeResponse(payload))
    with pytest.raises(ProviderError) as excinfo:
        await TikWMProvider(session).fetch("https://vm.tiktok.com/ZMhvzrfeR/")
    assert excinfo.value.retryable is False


def test_ytdlp_prefers_unwatermarked_high_quality() -> None:
    formats = [
        {
            "format_id": "play_addr-480",
            "url": "https://cdn/wm-480.mp4",
            "height": 480,
            "vcodec": "h264",
            "acodec": "aac",
        },
        {
            "format_id": "download_addr-1080",
            "url": "https://cdn/nowm-1080.mp4",
            "height": 1080,
            "vcodec": "h264",
            "acodec": "aac",
        },
        {
            "format_id": "download_addr-720",
            "url": "https://cdn/nowm-720.mp4",
            "height": 720,
            "vcodec": "h264",
            "acodec": "aac",
        },
        {
            "format_id": "audio",
            "url": "https://cdn/audio.m4a",
            "vcodec": "none",
            "acodec": "aac",
        },
    ]
    ordered = YtDlpProvider._pick_videos(formats)
    assert ordered[0] == "https://cdn/nowm-1080.mp4"
    assert ordered[1] == "https://cdn/nowm-720.mp4"
    assert ordered[2] == "https://cdn/wm-480.mp4"


def test_ytdlp_falls_back_to_watermarked_format() -> None:
    formats = [{"format_id": "play_addr-540", "url": "https://cdn/wm.mp4", "height": 540}]
    assert YtDlpProvider._pick_videos(formats) == ["https://cdn/wm.mp4"]


def test_media_result_helpers() -> None:
    result = MediaResult(
        video_id="1",
        provider="test",
        source_url="https://www.tiktok.com/@a/video/1",
        videos=["https://cdn/a.mp4", "https://cdn/a.mp4"],
        author="someone",
    )
    assert result.has_media
    assert result.video_candidates() == ["https://cdn/a.mp4"]
    assert result.profile_url == "https://www.tiktok.com/@someone"
    assert result.to_debug_dict()["provider"] == "test"
