"""Opt-in, overlap-safe scheduler for asynchronous read-only refresh callbacks.

No DJI credentials or network transport are instantiated automatically.
A caller must explicitly supply the read-only refresh coroutine.
"""
import asyncio
from collections.abc import Awaitable, Callable

from .status_runtime import StatusRuntime, utc_now


class ReadOnlyStatusPoller:
    def __init__(self, runtime: StatusRuntime,
                 refresh: Callable[[], Awaitable[object]]):
        if not isinstance(runtime, StatusRuntime) or not callable(refresh):
            raise TypeError("StatusRuntime and async refresh callback required")
        self.runtime = runtime
        self.refresh = refresh
        self._lock = asyncio.Lock()

    async def refresh_once(self) -> bool:
        """Make one isolated refresh attempt, never expose exception messages."""
        if self._lock.locked():
            return False
        async with self._lock:
            self.runtime.last_refresh_at = utc_now()
            self.runtime.polling = "running"
            try:
                await self.refresh()
            except asyncio.CancelledError:
                self.runtime.polling = "stopped"
                raise
            except Exception:
                # Never copy provider exception text: it could contain secrets.
                self.runtime.polling = "error"
                return False
            self.runtime.polling = "idle"
            self.runtime.last_refresh_success_at = utc_now()
            return True

    async def run(self, stop_event: asyncio.Event) -> None:
        """Poll immediately, then periodically until explicitly stopped."""
        if not isinstance(stop_event, asyncio.Event):
            raise TypeError("asyncio.Event required")
        try:
            while not stop_event.is_set():
                await self.refresh_once()
                try:
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=self.runtime.settings.refresh_every_seconds,
                    )
                except TimeoutError:
                    pass
        finally:
            self.runtime.polling = "stopped"
