"""Real OS-lock regressions: independent services, processes, failure and exit."""
import subprocess
import sys
import threading

import pytest

from aeronexus.processing_slot import ProcessingSlot
from test_multispectral import ms  # noqa: F401  (fixture)
from test_thermal import sdk_dir  # noqa: F401  (fixture)


def child_lock(root, *, crash=False):
    return subprocess.run(
        [sys.executable, "-c", """
import os, sys
from pathlib import Path
from aeronexus.processing_slot import ProcessingSlot
slot = ProcessingSlot(Path(sys.argv[1]))
got = slot.acquire(timeout=0.1)
print(got, flush=True)
if sys.argv[2] == 'crash':
    os._exit(7)
if got:
    slot.release()
""", str(root), "crash" if crash else "normal"],
        capture_output=True, text=True, timeout=5, check=False)


def test_processes_share_slot_and_kernel_releases_on_crash(tmp_path):
    root = tmp_path / "ws"
    slot = ProcessingSlot(root)
    with slot:
        child = child_lock(root)
        assert child.returncode == 0 and child.stdout.strip() == "False", child.stderr
    child = child_lock(root, crash=True)
    assert child.returncode == 7 and child.stdout.strip() == "True", child.stderr
    with slot:  # no stale PID file after abnormal child termination
        assert (root / "image-processing.lock").stat().st_mode & 0o077 == 0


def test_instances_and_threads_share_slot_and_release_after_exception(tmp_path):
    first, second = ProcessingSlot(tmp_path / "ws"), ProcessingSlot(tmp_path / "ws")
    with pytest.raises(ValueError):
        with first:
            result = []
            thread = threading.Thread(target=lambda: result.append(second.acquire(timeout=0.05)))
            thread.start()
            thread.join(2)
            assert not thread.is_alive() and result == [False]
            raise ValueError("calculation failed")
    assert second.acquire(timeout=0.1)
    second.release()


def test_lock_rejects_symlinks_without_touching_target(tmp_path):
    root = tmp_path / "ws"
    root.mkdir(mode=0o700)
    target = tmp_path / "untouched"
    target.write_text("private")
    (root / "image-processing.lock").symlink_to(target)
    slot = ProcessingSlot(root)
    for _ in range(2):  # failed opens must not leave the thread gate held
        with pytest.raises(OSError, match="processing lock unavailable"):
            slot.acquire(timeout=0)
    assert target.read_text() == "private"


def test_multispectral_and_sdk_use_same_workspace_lock(ms, sdk_dir):
    from aeronexus.multispectral import MultispectralService
    from aeronexus.thermal_sdk import ThermalSdk
    other = MultispectralService(ms.media)
    sdk = ThermalSdk.from_env()
    with ms._compute:
        assert not other._compute.acquire(timeout=0)
        assert not sdk._processing.acquire(timeout=0)
    assert sdk._processing.acquire(timeout=0)
    sdk._processing.release()


def test_sdk_cannot_start_while_multispectral_is_processing(ms, sdk_dir, monkeypatch):
    from aeronexus.thermal_sdk import ThermalSdk, ThermalSdkBusy, ThermalSdkError
    sdk = ThermalSdk.from_env()
    sdk.PROCESSING_WAIT_SECONDS = 0.05
    called = []
    def fail(*args, **kwargs):
        called.append(True)
        raise subprocess.TimeoutExpired("private tool path", 90)
    monkeypatch.setattr("aeronexus.thermal_sdk.subprocess.run", fail)
    with ms._compute:
        with pytest.raises(ThermalSdkBusy):
            sdk._run(["-V"], str(sdk_dir))
    assert not called
    with pytest.raises(ThermalSdkError, match="timed out"):
        sdk._run(["-V"], str(sdk_dir))
    assert called == [True]
    # A failing SDK child must release both gates, including the process lock.
    with ms._compute:
        pass
    assert sdk._slots.acquire(timeout=0)
    sdk._slots.release()
