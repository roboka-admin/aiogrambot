import pytest
from aiohttp import ClientSession

from core.health import start_health_server, stop_health_server


@pytest.mark.asyncio
async def test_health_server_not_started_without_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PORT", raising=False)

    assert await start_health_server() is None
    await stop_health_server(None)  # must be a no-op


@pytest.mark.asyncio
async def test_health_server_serves_ok_when_port_is_set(
    monkeypatch: pytest.MonkeyPatch, unused_tcp_port: int
) -> None:
    monkeypatch.setenv("PORT", str(unused_tcp_port))

    runner = await start_health_server()
    assert runner is not None
    try:
        async with ClientSession() as session:
            for path in ("/", "/health"):
                async with session.get(f"http://127.0.0.1:{unused_tcp_port}{path}") as response:
                    assert response.status == 200
                    assert await response.text() == "ok"
    finally:
        await stop_health_server(runner)


@pytest.mark.asyncio
async def test_health_server_does_not_emit_access_log(
    monkeypatch: pytest.MonkeyPatch, unused_tcp_port: int, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("PORT", str(unused_tcp_port))

    runner = await start_health_server()
    assert runner is not None
    try:
        with caplog.at_level("INFO", logger="aiohttp.access"):
            async with ClientSession() as session:
                async with session.get(f"http://127.0.0.1:{unused_tcp_port}/") as response:
                    assert response.status == 200
    finally:
        await stop_health_server(runner)

    assert not [record for record in caplog.records if record.name == "aiohttp.access"]
