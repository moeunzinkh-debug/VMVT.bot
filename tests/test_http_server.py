"""Tests for the health / status / webhook HTTP server."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from telegram import Bot

from bot.http_server import HttpServer

UPDATE_PAYLOAD = {
    "update_id": 123,
    "message": {
        "message_id": 7,
        "date": 1_700_000_000,
        "chat": {"id": 42, "type": "private"},
        "text": "https://vm.tiktok.com/ZMhvzrfeR/",
    },
}


async def start_server(settings, application=None, **overrides) -> tuple[HttpServer, int]:
    # port 0 = let the OS pick a free port so the tests never clash
    settings = replace(settings, port=0, host="127.0.0.1", **overrides)
    server = HttpServer(settings, application)
    await server.start()
    socket = server._site._server.sockets[0]
    return server, socket.getsockname()[1]


@pytest.mark.asyncio
async def test_health_endpoint_reports_status(settings) -> None:
    server, port = await start_server(settings)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://127.0.0.1:{port}/healthz") as response:
                assert response.status == 200
                payload = await response.json()
            async with session.get(f"http://127.0.0.1:{port}/") as response:
                assert response.status == 200
                body = await response.text()
    finally:
        await server.stop()

    assert payload["status"] == "ok"
    assert payload["mode"] == settings.mode
    assert "VMVT.bot" in body


@pytest.mark.asyncio
async def test_webhook_route_processes_updates(settings) -> None:
    application = MagicMock()
    application.bot = Bot("123456:TEST-TOKEN")  # a real bot object so Update.de_json works
    application.bot_data = {}
    application.process_update = AsyncMock()

    server, port = await start_server(settings, application, webhook_secret="top-secret")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://127.0.0.1:{port}{settings.webhook_path}",
                json=UPDATE_PAYLOAD,
                headers={"X-Telegram-Bot-Api-Secret-Token": "top-secret"},
            ) as response:
                assert response.status == 200
                assert await response.json() == {"ok": True}

            async with session.post(
                f"http://127.0.0.1:{port}{settings.webhook_path}",
                json=UPDATE_PAYLOAD,
            ) as response:
                assert response.status == 401

            async with session.post(
                f"http://127.0.0.1:{port}{settings.webhook_path}",
                data="not-json",
                headers={"X-Telegram-Bot-Api-Secret-Token": "top-secret"},
            ) as response:
                assert response.status == 400

        # processing happens in a background task, give it a moment
        for _ in range(50):
            if application.process_update.await_count:
                break
            import asyncio

            await asyncio.sleep(0.02)
    finally:
        await server.stop()

    application.process_update.assert_awaited_once()
    update = application.process_update.await_args.args[0]
    assert update.update_id == 123
    assert update.effective_message.text.endswith("ZMhvzrfeR/")


@pytest.mark.asyncio
async def test_webhook_route_not_registered_without_application(settings) -> None:
    server, port = await start_server(settings)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"http://127.0.0.1:{port}/webhook", json={}) as response:
                assert response.status == 404
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_stats_endpoint_includes_service_information(settings) -> None:
    application = MagicMock()
    application.bot_data = {"tiktok_service": MagicMock(stats=lambda: {"providers": ["tikwm"]})}
    server, port = await start_server(settings, application)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://127.0.0.1:{port}/stats") as response:
                payload = await response.json()
    finally:
        await server.stop()
    assert payload["providers"] == ["tikwm"]
