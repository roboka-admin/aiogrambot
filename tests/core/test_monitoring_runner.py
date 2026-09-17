import asyncio

import pytest

from core import monitoring_runner


class FlakyService:
    def __init__(self) -> None:
        self.cycles = 0

    async def run_cycle(self):
        self.cycles += 1
        if self.cycles == 1:
            raise RuntimeError("first cycle explodes")
        return None, []


@pytest.mark.asyncio
async def test_loop_survives_cycle_errors_and_stops_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    real_sleep = asyncio.sleep

    async def fast_sleep(_: float) -> None:
        await real_sleep(0)

    monkeypatch.setattr(monitoring_runner.asyncio, "sleep", fast_sleep)
    service = FlakyService()

    task = monitoring_runner.start_monitoring(service, interval_seconds=300)  # type: ignore[arg-type]
    for _ in range(20):
        await real_sleep(0)
    await monitoring_runner.stop_monitoring(task)

    assert service.cycles >= 2
    assert task.cancelled()


@pytest.mark.asyncio
async def test_stop_monitoring_accepts_none() -> None:
    await monitoring_runner.stop_monitoring(None)
