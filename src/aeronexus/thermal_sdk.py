"""DJI Thermal SDK (TSDK) adapter: radiometric R-JPEG -> temperature grid.

The SDK is proprietary (DJI license) and is never vendored into this
repository. It is installed locally (deploy/pi/install-thermal-sdk.sh) and
called only as a separate process through its sample tool ``dji_irp``, so
``libdirp`` is never linked into the web server.

DJI ships Linux builds for x86/x64 only. On the Raspberry Pi 5 (ARM64,
16 KiB pages) qemu-user cannot map the SDK libraries; Box64 can. The runner
is therefore ``native`` on x86_64 and ``box64`` elsewhere. Box64 from Debian
does not wrap libstdc++/libgcc_s/libgomp, so their x86_64 builds are loaded
from a private directory (AERONEXUS_BOX64_X86_LIBS).

Only the measurement action is used. Originals are written to a private
temporary directory, never modified, and the SDK never sees credentials:
the child process gets a minimal environment.
"""
from __future__ import annotations

from array import array
from dataclasses import dataclass
import math
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading


class ThermalSdkError(RuntimeError):
    """Safe for HTTP details: never contains paths, stdout or file names."""


class ThermalSdkUnavailable(ThermalSdkError):
    pass


class ThermalSdkBusy(ThermalSdkError):
    pass


# dji_irp v1.8 "get params range" (identical for M3T/M30T/M4T images).
PARAM_RANGES = {
    "distance": (1.0, 25.0),      # m
    "humidity": (20.0, 100.0),    # % (CLI documents 20..100)
    "emissivity": (0.1, 1.0),
    "reflection": (-40.0, 100.0),  # reflected apparent temperature, deg C
    "ambient": (-40.0, 80.0),     # ambient temperature, deg C
}
MAX_IMAGE_BYTES = 16 * 1024 * 1024
MAX_DIMENSION = 4096
TEMPERATURE_LIMITS = (-100.0, 2000.0)
TIMEOUT_SECONDS = 90
_DEFAULT_BOX64_HOME = Path("~/.local/opt/aeronexus-box64").expanduser()


@dataclass(frozen=True)
class MeasureParams:
    """Optional overrides. ``None`` keeps the value stored in the R-JPEG."""
    distance: float | None = None
    humidity: float | None = None
    emissivity: float | None = None
    reflection: float | None = None
    ambient: float | None = None

    def __post_init__(self):
        for name, (low, high) in PARAM_RANGES.items():
            value = getattr(self, name)
            if value is None:
                continue
            if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{name} must be between {low:g} and {high:g}")
            object.__setattr__(self, name, round(float(value), 3))

    def arguments(self) -> list[str]:
        args = []
        for name in PARAM_RANGES:
            value = getattr(self, name)
            if value is not None:
                args += [f"--{name}", f"{value:g}"]
        return args

    def overrides(self) -> dict:
        return {name: getattr(self, name) for name in PARAM_RANGES
                if getattr(self, name) is not None}


@dataclass(frozen=True)
class ThermalSdkSettings:
    tool: Path
    lib_dir: Path
    runner: str             # "native" | "box64"
    box64: Path | None
    x86_libs: Path | None

    @classmethod
    def from_env(cls, environ=None) -> "ThermalSdkSettings":
        env = os.environ if environ is None else environ
        home = env.get("AERONEXUS_DJI_TSDK_DIR", "").strip()
        if not home:
            raise ThermalSdkUnavailable("DJI Thermal SDK is not configured")
        tool, lib_dir = _locate(Path(home).expanduser())
        runner = env.get("AERONEXUS_DJI_TSDK_RUNNER", "auto").strip() or "auto"
        if runner not in ("auto", "native", "box64"):
            raise ThermalSdkUnavailable("AERONEXUS_DJI_TSDK_RUNNER must be auto, native or box64")
        if runner == "auto":
            runner = "native" if platform.machine() in ("x86_64", "AMD64", "amd64") else "box64"
        if runner == "native":
            return cls(tool, lib_dir, runner, None, None)
        box64 = env.get("AERONEXUS_BOX64", "").strip()
        box64_path = (Path(box64).expanduser() if box64 else
                      _first_file(_DEFAULT_BOX64_HOME / "usr/bin/box64",
                                  Path(shutil.which("box64") or "/nonexistent")))
        if box64_path is None or not box64_path.is_file() or not os.access(box64_path, os.X_OK):
            raise ThermalSdkUnavailable("Box64 is required to run the x64 DJI Thermal SDK on this CPU")
        libs = env.get("AERONEXUS_BOX64_X86_LIBS", "").strip()
        x86 = Path(libs).expanduser() if libs else _DEFAULT_BOX64_HOME / "x86libs"
        if not (x86 / "libstdc++.so.6").is_file():
            raise ThermalSdkUnavailable("x86_64 libstdc++ for Box64 is missing")
        return cls(tool, lib_dir, runner, box64_path, x86)

    def command(self, *args: str) -> list[str]:
        prefix = [str(self.box64)] if self.runner == "box64" else []
        return [*prefix, str(self.tool), *args]

    def child_env(self, workdir: str) -> dict:
        # Minimal environment: no AERONEXUS_* secrets, tokens or proxies.
        env = {"PATH": "/usr/bin:/bin", "HOME": workdir, "LANG": "C", "LC_ALL": "C",
               "LD_LIBRARY_PATH": str(self.lib_dir)}
        if self.runner == "box64":
            env.update({"BOX64_LD_LIBRARY_PATH": f"{self.lib_dir}:{self.x86_libs}",
                        "BOX64_LOG": "0", "BOX64_NOBANNER": "1"})
        return env


def _first_file(*paths: Path) -> Path | None:
    return next((p for p in paths if p.is_file()), None)


def _locate(home: Path) -> tuple[Path, Path]:
    """Accept a flat bin directory or the extracted DJI SDK layout."""
    if not home.is_absolute():
        raise ThermalSdkUnavailable("AERONEXUS_DJI_TSDK_DIR must be an absolute path")
    candidates = (
        (home / "dji_irp", home),
        (home / "bin/dji_irp", home / "bin"),
        (home / "utility/bin/linux/release_x64/dji_irp", home / "tsdk-core/lib/linux/release_x64"),
    )
    for tool, lib_dir in candidates:
        if tool.is_file() and (lib_dir / "libdirp.so").is_file():
            return tool, lib_dir
    raise ThermalSdkUnavailable("dji_irp and libdirp.so not found in AERONEXUS_DJI_TSDK_DIR")


_DIM_RE = {k: re.compile(rf"image\s+{k}\s*:\s*(\d+)") for k in ("width", "height")}
_RC_RE = re.compile(r"return code\s+(-?\d+)")
_VERSION_RE = re.compile(r"(?:DIRP API version number|APP version)\s*:\s*(\S+)")


class ThermalSdk:
    """Thread-safe, single-flight dji_irp runner (the Pi has 4 cores)."""

    def __init__(self, settings: ThermalSdkSettings, *, max_parallel: int = 1):
        self.settings = settings
        self._slots = threading.BoundedSemaphore(max_parallel)
        self._version: dict | None = None

    @classmethod
    def from_env(cls, environ=None) -> "ThermalSdk":
        return cls(ThermalSdkSettings.from_env(environ))

    def _run(self, args: list[str], workdir: str) -> subprocess.CompletedProcess:
        if not self._slots.acquire(timeout=30):
            raise ThermalSdkBusy("DJI Thermal SDK is busy")
        try:
            return subprocess.run(
                self.settings.command(*args), cwd=workdir, env=self.settings.child_env(workdir),
                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                errors="replace", timeout=TIMEOUT_SECONDS, check=False)
        except subprocess.TimeoutExpired as exc:
            raise ThermalSdkError("DJI Thermal SDK timed out") from exc
        except OSError as exc:
            raise ThermalSdkUnavailable("DJI Thermal SDK could not be started") from exc
        finally:
            self._slots.release()

    def version(self) -> dict:
        if self._version is None:
            with tempfile.TemporaryDirectory(prefix="aeronexus-tsdk-") as tmp:
                proc = self._run(["-V"], tmp)
            found = dict((m.group(0).split(":")[0].strip(), m.group(1))
                         for m in _VERSION_RE.finditer(proc.stdout + proc.stderr))
            if proc.returncode != 0 or not found:
                raise ThermalSdkUnavailable("DJI Thermal SDK did not report a version")
            self._version = {"tool": found.get("APP version"),
                             "dirp_api": found.get("DIRP API version number"),
                             "runner": self.settings.runner}
        return self._version

    def measure(self, jpeg: bytes, params: MeasureParams | None = None) -> tuple[int, int, array]:
        """Return (width, height, float32 deg C, row-major)."""
        if not isinstance(jpeg, (bytes, bytearray)) or not 4 <= len(jpeg) <= MAX_IMAGE_BYTES:
            raise ThermalSdkError("R-JPEG missing or too large")
        if jpeg[:2] != b"\xff\xd8":
            raise ThermalSdkError("Not a JPEG image")
        params = params or MeasureParams()
        with tempfile.TemporaryDirectory(prefix="aeronexus-tsdk-") as tmp:
            src, out = Path(tmp, "input.jpg"), Path(tmp, "temperature.raw")
            fd = os.open(src, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(jpeg)
            proc = self._run(["-s", src.name, "-a", "measure", "-o", out.name,
                              "--measurefmt", "float32", *params.arguments()], tmp)
            text = proc.stdout + proc.stderr
            code = _RC_RE.search(text)
            if proc.returncode != 0 or (code and code.group(1) != "0") or not out.is_file():
                detail = f" (code {code.group(1)})" if code else f" (exit {proc.returncode})"
                raise ThermalSdkError("DJI Thermal SDK could not measure this image" + detail)
            dims = [m.search(text) for m in _DIM_RE.values()]
            if not all(dims):
                raise ThermalSdkError("DJI Thermal SDK did not report the image size")
            width, height = (int(m.group(1)) for m in dims)
            if not (0 < width <= MAX_DIMENSION and 0 < height <= MAX_DIMENSION):
                raise ThermalSdkError("Unsupported thermal resolution")
            raw = out.read_bytes()
        if len(raw) != width * height * 4:
            raise ThermalSdkError("Unexpected DJI Thermal SDK output size")
        grid = array("f")
        grid.frombytes(raw)
        if sys.byteorder != "little":
            grid.byteswap()
        low, high = TEMPERATURE_LIMITS
        if not all(low <= value <= high for value in grid):  # also rejects NaN
            raise ThermalSdkError("DJI Thermal SDK returned implausible temperatures")
        return width, height, grid


def sdk_status(environ=None) -> dict:
    """Readiness for the UI, without paths or exception internals."""
    try:
        sdk = ThermalSdk.from_env(environ)
        return {"available": True, **sdk.version()}
    except ThermalSdkError as exc:
        return {"available": False, "reason": str(exc)}
