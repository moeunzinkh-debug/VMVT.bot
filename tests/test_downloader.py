"""Tests for the downloader facade."""

from __future__ import annotations

import asyncio

import pytest
from conftest import FakeDownloadResponse, FakeDownloadSession, FakeResponse, FakeSession

from bot.services import (
    DownloadError,
    MediaTooLargeError,
    ResolveError,
    TikTokService,
)
from bot.services.providers import MediaResult, ProviderError


class FakeProvider:
    def __init__(self, result: MediaResult | None = None, error: Exception | None = None):
        self.name = "fake"
        self.result = result
        self.error = error
        self.calls = 0

    async def fetch(self, url: str) -> MediaResult:
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def make_service(settings, session) -> TikTokService:
    service = TikTokService(settings, session)
    service._providers = []
    return service


@pytest.mark.asyncio
async def test_download_streams_to_disk(settings) -> None:
    chunks = [b"1234" * 256, b"5678" * 128]
    session = FakeDownloadSession(FakeDownloadResponse(chunks))
    service = make_service(settings, session)

    downloaded = await service.download("https://cdn/x.mp4", max_bytes=10_000_000)

    assert downloaded.size == sum(len(c) for c in chunks)
    assert downloaded.path.read_bytes() == b"".join(chunks)
    assert downloaded.content_type == "video/mp4"
    assert downloaded.is_image is False
    downloaded.cleanup()
    assert not downloaded.path.exists()


@pytest.mark.asyncio
async def test_download_rejects_declared_oversized_media(settings) -> None:
    session = FakeDownloadSession(FakeDownloadResponse([b"x" * 100], content_length=99_000_000))
    service = make_service(settings, session)

    with pytest.raises(MediaTooLargeError):
        await service.download("https://cdn/x.mp4", max_bytes=1024)


@pytest.mark.asyncio
async def test_download_aborts_when_stream_exceeds_limit(settings) -> None:
    session = FakeDownloadSession(FakeDownloadResponse([b"x" * 4096, b"y" * 4096]))
    service = make_service(settings, session)

    with pytest.raises(MediaTooLargeError):
        await service.download("https://cdn/x.mp4", max_bytes=2048)

    assert not any(settings.temp_dir.iterdir())


@pytest.mark.asyncio
async def test_download_rejects_html_error_pages(settings) -> None:
    session = FakeDownloadSession(
        FakeDownloadResponse([b"<html>403</html>"], content_type="text/html")
    )
    service = make_service(settings, session)

    with pytest.raises(DownloadError, match="Unexpected content type"):
        await service.download("https://cdn/x.mp4", max_bytes=1024)


@pytest.mark.asyncio
async def test_download_rejects_http_errors(settings) -> None:
    session = FakeDownloadSession(FakeDownloadResponse([b""], status=404))
    service = make_service(settings, session)

    with pytest.raises(DownloadError, match="404"):
        await service.download("https://cdn/x.mp4", max_bytes=1024)


@pytest.mark.asyncio
async def test_download_rejects_empty_files(settings) -> None:
    session = FakeDownloadSession(FakeDownloadResponse([]))
    service = make_service(settings, session)

    with pytest.raises(DownloadError, match="empty"):
        await service.download("https://cdn/x.mp4", max_bytes=1024)


@pytest.mark.asyncio
async def test_resolve_uses_first_working_provider(settings) -> None:
    session = FakeSession(FakeResponse({}))
    service = make_service(settings, session)
    expected = MediaResult(
        video_id="7123456789012345678", provider="a", source_url="u", videos=["https://cdn/a.mp4"]
    )
    service._providers = [
        FakeProvider(error=ProviderError("boom", provider="a")),
        FakeProvider(result=expected),
    ]

    result = await service.resolve("https://www.tiktok.com/@u/video/7123456789012345678")
    assert result is expected


@pytest.mark.asyncio
async def test_resolve_raises_when_all_providers_fail(settings) -> None:
    session = FakeSession(FakeResponse({}))
    service = make_service(settings, session)
    service._providers = [
        FakeProvider(error=ProviderError("down", provider="a")),
        FakeProvider(error=ProviderError("gone", provider="b", retryable=False)),
    ]

    with pytest.raises(ResolveError) as excinfo:
        await service.resolve("https://www.tiktok.com/@u/video/7123456789012345678")
    assert "down" in str(excinfo.value)


@pytest.mark.asyncio
async def test_resolve_caches_results(settings) -> None:
    session = FakeSession(FakeResponse({}))
    service = make_service(settings, session)
    provider = FakeProvider(
        result=MediaResult(
            video_id="7123456789012345678", provider="a", source_url="u", videos=["https://cdn/a"]
        )
    )
    service._providers = [provider]

    url = "https://www.tiktok.com/@u/video/7123456789012345678"
    await service.resolve(url)
    await service.resolve(f"{url}?extra=1")

    assert provider.calls == 1
    assert service.stats()["resolve_cache"] == 1


@pytest.mark.asyncio
async def test_resolve_raises_without_providers(settings) -> None:
    service = make_service(settings, FakeSession(FakeResponse({})))
    with pytest.raises(ResolveError, match="No download providers"):
        await service.resolve("https://vm.tiktok.com/ZMhvzrfeR/")


@pytest.mark.asyncio
async def test_service_reports_enabled_providers(settings) -> None:
    service = TikTokService(settings, FakeSession(FakeResponse({})))
    assert set(service.stats()["providers"]) >= {"tikwm", "ytdlp"}


def test_downloaded_file_cleanup_is_safe(tmp_path) -> None:
    from bot.services.downloader import DownloadedFile

    target = tmp_path / "a.mp4"
    target.write_bytes(b"data")
    file = DownloadedFile(path=target, size=4, content_type="video/mp4", url="u")
    file.cleanup()
    file.cleanup()  # second call must not raise
    assert not target.exists()


def test_event_loop_helpers_are_importable() -> None:
    # sanity check that the module has no top-level side effects
    import bot.services.downloader as module

    assert issubclass(module.MediaTooLargeError, module.DownloadError)
    assert isinstance(asyncio.TimeoutError, type)
