import asyncio

import pytest

from core import retention_runner


class FlakyService:
    def __init__(self) -> None:
        self.runs = 0

    async def run_once(self):
        self.runs += 1
        if self.runs == 1:
            raise RuntimeError("first run explodes")


@pytest.mark.asyncio
async def test_loop_survives_errors_and_stops_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    real_sleep = asyncio.sleep

    async def fast_sleep(_: float) -> None:
        await real_sleep(0)

    monkeypatch.setattr(retention_runner.asyncio, "sleep", fast_sleep)
    service = FlakyService()

    task = retention_runner.start_retention(service, interval_seconds=3600)  # type: ignore[arg-type]
    for _ in range(20):
        await real_sleep(0)
    await retention_runner.stop_retention(task)

    assert service.runs >= 2
    assert task.cancelled()


@pytest.mark.asyncio
async def test_stop_retention_accepts_none() -> None:
    await retention_runner.stop_retention(None)
