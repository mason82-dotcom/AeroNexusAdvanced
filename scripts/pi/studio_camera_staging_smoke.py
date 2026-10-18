#!/usr/bin/env python3
"""Launch an isolated localhost AeroNexusAdvanced camera-preview browser smoke.

Requires Python Playwright (use the separate browser venv) and a project
Python virtualenv with uvicorn installed. Starts an independent FastAPI
instance bound ONLY to 127.0.0.1, with a disposable synthetic workspace.
It intentionally does not load the production .env, use production Geo data,
call DJI, issue commands, or alter/restart the production service.

Browser requests are limited to localhost and published Leaflet/Esri/OSM
static assets. Only POST /api/v1/studio/survey/preview is permitted.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen
from uuid import UUID


TEST_ID = "00000000-0000-4000-8000-000000000001"
RECTANGLE = [
    {"latitude": 49.15330, "longitude": 8.58400},
    {"latitude": 49.15330, "longitude": 8.58490},
    {"latitude": 49.15410, "longitude": 8.58490},
    {"latitude": 49.15410, "longitude": 8.58400},
]
PROFILE = "matrice-4e-wide"
BROWSER_EXTERNAL_HOSTS = frozenset((
    "cdn.jsdelivr.net", "server.arcgisonline.com", "tile.openstreetmap.org",
))


class StagingSmokeError(RuntimeError):
    pass


def isolated_env(workspace: Path, checkout: Path, host: str = "192.168.178.63") -> dict:
    """Pass no deployment credentials, tokens, proxy variables, or .env to staging."""
    # Never expose the user's real HOME to the test server. Several read-only
    # adapters look for credential/session files under ~/.config by default.
    # A disposable HOME prevents touching those files even during page loads.
    isolated_home = workspace.parent / "home"
    isolated_home.mkdir(mode=0o700, exist_ok=True)
    clean = {key: os.environ[key] for key in
             ("PATH", "LANG", "LC_ALL", "TZ")
             if key in os.environ}
    clean.update({
        "HOME": str(isolated_home),
        "PYTHONPATH": str(checkout / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "AERONEXUS_WORKSPACE_DIR": str(workspace),
        "AERONEXUS_LAN_NO_TOKEN": "1",
        "AERONEXUS_LAN_HOST": host,
    })
    return clean


def seed_synthetic_workspace(workspace: Path) -> None:
    workspace.mkdir(mode=0o700, parents=True, exist_ok=False)
    for dirname in ("geo_objects", "missions", "media"):
        (workspace / dirname).mkdir(mode=0o700)
    payload = {
        "id": TEST_ID,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "object": {
            "name": "Synthetic camera geometry (staging only)",
            "kind": "polygon",
            "vertices": RECTANGLE,
            "radius_m": None,
        },
    }
    path = workspace / "geo_objects" / f"{TEST_ID}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(0o600)


def ensure_unused_loopback_port(port: int) -> None:
    if not 1024 <= port <= 65535:
        raise StagingSmokeError("Staging port must be between 1024 and 65535")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            raise StagingSmokeError("Requested loopback port already in use") from None


@contextmanager
def staging_server(python: Path, checkout: Path, workspace: Path, port: int):
    if not python.is_file():
        raise StagingSmokeError("Project Python missing; use --server-python")
    ensure_unused_loopback_port(port)
    origin = f"http://127.0.0.1:{port}"
    env = isolated_env(workspace, checkout)
    with (workspace / "server.log").open("wb") as logs:
        server = subprocess.Popen(
            [str(python), "-m", "uvicorn", "aeronexus.app:app",
             "--host", "127.0.0.1", "--port", str(port),
             "--no-access-log", "--no-server-header"],
            env=env, cwd=str(checkout), stdin=subprocess.DEVNULL,
            stdout=logs, stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(80):
                if server.poll() is not None:
                    raise StagingSmokeError(
                        "Isolated staging server exited before becoming healthy")
                try:
                    with urlopen(origin + "/health", timeout=0.5) as response:
                        data = json.load(response)
                    if data.get("status") == "ok":
                        break
                except (OSError, URLError, ValueError):
                    pass
                time.sleep(0.25)
            else:
                raise StagingSmokeError("Staging server health timeout")
            yield origin
        finally:
            server.terminate()
            try:
                server.wait(timeout=8)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=8)


def browser_request_allowed(method: str, url: str, origin: str) -> bool:
    from urllib.parse import urlsplit
    parts = urlsplit(url)
    method = method.upper()
    if url.startswith(origin + "/"):
        return method in ("GET", "HEAD", "OPTIONS") or (
            method == "POST" and parts.path == "/api/v1/studio/survey/preview"
            and parts.query == "")
    if parts.scheme == "https" and parts.hostname in BROWSER_EXTERNAL_HOSTS:
        return method == "GET"
    return False


def validate_result(data: dict) -> tuple[int, float, dict]:
    if data.get("kind") != "survey-preview":
        raise StagingSmokeError("Invalid survey response kind")
    legs = data.get("legs", [])
    count = data.get("leg_count")
    distance = data.get("distance_m")
    camera = data.get("camera_plan", {})
    if (not isinstance(count, int) or isinstance(count, bool)
            or not 1 <= count <= 200 or len(legs) != count):
        raise StagingSmokeError("Invalid survey leg count")
    if (not isinstance(distance, (float, int)) or not math.isfinite(distance)
            or distance <= 0 or not isinstance(camera, dict)
            or camera.get("profile_id") != PROFILE):
        raise StagingSmokeError("Missing or invalid real camera optics")
    for metric in ("gsd_cm_px", "spacing_m", "trigger_interval_m"):
        value = camera.get(metric)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise StagingSmokeError(f"Invalid camera metric: {metric}")
    if "waypoints" in data or "flight_commands" in data:
        raise StagingSmokeError("Executable route appeared in preview response")
    return count, float(distance), camera


def run_browser(origin: str, screenshot: Path, require_tiles: bool):
    from playwright.sync_api import sync_playwright
    chromium = os.environ.get("AERONEXUS_CHROMIUM_BIN", "/usr/bin/chromium")
    if not Path(chromium).is_file():
        raise StagingSmokeError("Chromium executable missing")
    blocked = []
    seen_preview = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=chromium, headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            def filtered(route):
                req = route.request
                if browser_request_allowed(req.method, req.url, origin):
                    route.continue_()
                else:
                    blocked.append((req.method, req.url.split("?", 1)[0]))
                    route.abort()
            page.route("**/*", filtered)
            page.goto(origin + "/studio", wait_until="domcontentloaded",
                      timeout=25000)
            page.wait_for_function(
                "() => typeof L === 'object' && typeof map !== 'undefined' && !!map",
                timeout=25000)
            page.locator('nav button[data-tab="geo-pane"]').click()
            page.wait_for_function(
                """id => {
                  const select=document.querySelector('#survey-object');
                  return !!select && Array.from(select.options).some(o=>o.value===id)
                }""", arg=TEST_ID, timeout=15000)
            page.locator("#survey-object").select_option(TEST_ID)
            page.locator("#survey-camera").select_option(PROFILE)
            page.locator("#survey-height-agl").fill("60")
            page.locator("#survey-side-overlap").fill("70")
            page.locator("#survey-front-overlap").fill("80")
            with page.expect_response(
                lambda r: r.request.method == "POST"
                  and r.url == origin + "/api/v1/studio/survey/preview",
                timeout=25000) as response_ctx:
                page.locator("#survey-generate").click()
            result_response = response_ctx.value
            if result_response.status != 200:
                raise StagingSmokeError("Staging camera API returned non-200 HTTP")
            response = result_response.json()
            count, distance, camera = validate_result(response)
            seen_preview.append(True)
            page.wait_for_function(
                """n => typeof surveyLayer !== 'undefined' &&
                     !!surveyLayer && surveyLayer.getLayers().length === n &&
                     !document.getElementById('survey-camera-metrics').hidden""",
                arg=count, timeout=12000)
            svg = page.locator(
                "#map .leaflet-overlay-pane svg path[stroke='#ffab70']").count()
            if svg != count:
                raise StagingSmokeError("Staging Leaflet SVG count mismatch")
            panel = page.locator("#survey-camera-metrics").inner_text()
            if "GSD" not in panel or "Fotos" not in panel:
                raise StagingSmokeError("GSD or photo estimate missing in UI")
            if blocked:
                raise StagingSmokeError("Blocked unexpected external/mutating browser requests")
            if require_tiles:
                tile_count = page.locator(
                    "#map img.leaflet-tile-loaded").count()
                if tile_count == 0:
                    raise StagingSmokeError("No real map tile loaded (network needed)")
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshot), timeout=15000)
            print("Staging browser: PASS / real API + real Leaflet SVG")
            print("Camera:", PROFILE)
            print("Flight strips:", count)
            print("Independent strip length:", round(distance, 1), "m")
            print("GSD:", camera["gsd_cm_px"], "cm/pixel")
            print("Derived strip spacing:", camera["spacing_m"], "m")
            print("Estimated photos:", camera["estimated_photo_count"])
            print("Screenshot:", screenshot)
        finally:
            browser.close()
    if not seen_preview:
        raise StagingSmokeError("No preview API request observed")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-python", required=True, type=Path,
                        help="Existing project venv Python with uvicorn")
    parser.add_argument("--port", type=int, default=18081)
    parser.add_argument("--require-tiles", action="store_true",
                        help="Fail unless a real map tile loaded")
    parser.add_argument("--screenshot", type=Path,
                        default=Path("/tmp/aeronexus-camera-staging.png"))
    args = parser.parse_args(argv)
    checkout = Path(__file__).resolve().parents[2]
    try:
        with tempfile.TemporaryDirectory(prefix="aeronexus-camera-stage-") as base:
            workspace = Path(base) / "workspace"
            seed_synthetic_workspace(workspace)
            with staging_server(args.server_python, checkout, workspace, args.port) as origin:
                print("Staging server: healthy on loopback only")
                run_browser(origin, args.screenshot, args.require_tiles)
        print("Staging process stopped; synthetic workspace cleaned")
        return 0
    except (StagingSmokeError, OSError, ValueError) as exc:
        print("STAGING FAIL:", str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
