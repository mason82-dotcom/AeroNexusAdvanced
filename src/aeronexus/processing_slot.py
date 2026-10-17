"""One heavy image operation per workspace, across instances and processes.

The Pi web service and media-sync service share this advisory lock. Keep the
file in the private workspace (not /tmp: systemd PrivateTmp separates those
services). Never unlink it: replacing the inode would split the lock domain.
The kernel releases the lock after crashes; no PID files or stale-lock cleanup.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat
import threading
import time

from .studio_workspace import _private_dir


class ProcessingSlot:
    def __init__(self, root: Path | None = None):
        self.root = root or Path(os.environ.get(
            "AERONEXUS_WORKSPACE_DIR", "~/.local/share/aeronexusadvanced")).expanduser()
        self._gate = threading.Lock()
        self._fd: int | None = None

    def acquire(self, timeout: float = -1) -> bool:
        # flock works across independent opens, even within one process. The
        # gate also prevents two threads from overwriting this instance's fd.
        deadline = None if timeout < 0 else time.monotonic() + timeout
        if not self._gate.acquire(timeout=timeout):
            return False
        fd = None
        try:
            import fcntl  # Pi/Linux; fail closed on unsupported platforms
            root = _private_dir(self.root)
            fd = os.open(root / "image-processing.lock",
                         os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077
                    or info.st_uid != os.getuid() or info.st_nlink != 1):
                raise OSError("Invalid processing lock permissions")
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self._fd, fd = fd, None
                    return True
                except BlockingIOError:
                    remaining = None if deadline is None else deadline - time.monotonic()
                    if remaining is not None and remaining <= 0:
                        return False
                    threading.Event().wait(0.05 if remaining is None else min(0.05, remaining))
        except (ImportError, OSError, ValueError) as exc:
            raise OSError("Shared image processing lock unavailable") from exc
        finally:
            if fd is not None:
                os.close(fd)
            if self._fd is None:
                self._gate.release()

    def release(self) -> None:
        if self._fd is None:
            raise RuntimeError("Processing slot is not held")
        # Closing the independently opened descriptor releases its flock.
        try:
            os.close(self._fd)
        finally:
            self._fd = None
            self._gate.release()

    def __enter__(self):
        if not self.acquire(timeout=60):
            raise TimeoutError("Image processing busy; retry shortly")
        return self

    def __exit__(self, *exc):
        self.release()
