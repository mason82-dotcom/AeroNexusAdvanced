"""Opt-in read-only scheduler: errors and overlap never leak secrets."""
import asyncio
from datetime import timezone

import pytest

from aeronexus.status_polling import ReadOnlyStatusPoller
from aeronexus.status_runtime import StatusRuntime, StatusSettings


def test_single_success():
    calls = []
    async def job():
        calls.append(True)
    rt = StatusRuntime(settings=StatusSettings(90, 5))
    poller = ReadOnlyStatusPoller(rt, job)
    assert asyncio.run(poller.refresh_once()) is True
    assert calls == [True]
    assert rt.polling == "idle"
    assert rt.last_refresh_at is not None
    assert rt.last_refresh_success_at is not None
    assert rt.last_refresh_at.tzinfo == timezone.utc


def test_failure_does_not_expose_exception_or_success():
    async def job():
        raise RuntimeError("secret DJI token leaked here")
    rt = StatusRuntime()
    poller = ReadOnlyStatusPoller(rt, job)
    assert asyncio.run(poller.refresh_once()) is False
    assert rt.polling == "error"
    assert rt.last_refresh_success_at is None
    assert "secret" not in str(rt.summary())


def test_failed_refresh_keeps_prior_success():
    calls = 0
    async def job():
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("redacted")
    rt = StatusRuntime()
    poller = ReadOnlyStatusPoller(rt, job)
    async def run():
        assert await poller.refresh_once() is True
        previous = rt.last_refresh_success_at
        assert await poller.refresh_once() is False
        assert rt.last_refresh_success_at == previous
    asyncio.run(run())


def test_no_overlapping_fetch():
    async def scenario():
        entered = asyncio.Event()
        release = asyncio.Event()
        calls = []
        async def job():
            calls.append(1)
            entered.set()
            await release.wait()
        rt = StatusRuntime()
        poller = ReadOnlyStatusPoller(rt, job)
        first = asyncio.create_task(poller.refresh_once())
        await entered.wait()
        assert await poller.refresh_once() is False
        release.set()
        assert await first is True
        assert calls == [1]
    asyncio.run(scenario())


def test_run_stops_on_event():
    async def scenario():
        stop = asyncio.Event()
        calls = []
        async def job():
            calls.append(1)
            stop.set()
        rt = StatusRuntime(settings=StatusSettings(90, 5))
        poller = ReadOnlyStatusPoller(rt, job)
        await poller.run(stop)
        assert calls == [1]
        assert rt.polling == "stopped"
        assert rt.last_refresh_success_at is not None
    asyncio.run(scenario())


def test_run_rejects_bad_event():
    async def job():
        pass
    async def scenario():
        with pytest.raises(TypeError):
            await ReadOnlyStatusPoller(StatusRuntime(), job).run(None)
    asyncio.run(scenario())


def test_constructor_validation():
    async def job():
        pass
    with pytest.raises(TypeError):
        ReadOnlyStatusPoller(None, job)
    with pytest.raises(TypeError):
        ReadOnlyStatusPoller(StatusRuntime(), None)


def test_cancellation_propagates():
    async def scenario():
        entered = asyncio.Event()
        async def job():
            entered.set()
            await asyncio.Event().wait()
        rt = StatusRuntime()
        poller = ReadOnlyStatusPoller(rt, job)
        task = asyncio.create_task(poller.refresh_once())
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert rt.polling == "stopped"
    asyncio.run(scenario())
