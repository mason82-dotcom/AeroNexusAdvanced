#!/usr/bin/env python3
"""Read-only HTTPS smoke for the productive AeroNexusAdvanced survey UI.

From a Raspberry Pi worktree, pass the deployed instance's trusted ca.crt.
Uses only GET /health, GET /studio, GET /api/v1/studio/geo-objects and
POST /api/v1/studio/survey/preview (a non-persisting calculation endpoint).
The optional Chromium interaction clicks only "Flugstreifen berechnen".
No mission save, flight command, DJI login, or service restart is performed.
Coordinates, object names and tokens are never printed.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import ssl
import subprocess
import sys
from urllib import error, request


ORIGIN = "https://192.168.178.63:8000"
MAX_REPLY_BYTES = 2 * 1024 * 1024
RECTANGLE = [
    {"latitude": 49.15330, "longitude": 8.58400},
    {"latitude": 49.15330, "longitude": 8.58490},
    {"latitude": 49.15410, "longitude": 8.58490},
    {"latitude": 49.15410, "longitude": 8.58400},
]
ALLOWED_HTTP = frozenset({
    ("GET", "/health"),
    ("GET", "/studio"),
    ("GET", "/api/v1/studio/geo-objects"),
    ("POST", "/api/v1/studio/survey/preview"),
})


class LiveSmokeError(Exception):
    """Intentional, non-sensitive diagnostic text."""


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise LiveSmokeError("Unexpected redirect blocked")


def build_opener(ca: Path):
    if not ca.is_file():
        raise LiveSmokeError("Local CA certificate not found; specify --ca")
    context = ssl.create_default_context(cafile=str(ca))
    return request.build_opener(request.HTTPSHandler(context=context), NoRedirect())


def call_api(opener, method: str, path: str, payload: dict | None = None):
    if (method, path) not in ALLOWED_HTTP:
        raise LiveSmokeError("Non-allowlisted API request refused")
    body = json.dumps(payload, allow_nan=False).encode() if payload is not None else None
    headers = {"Accept": "application/json", "Cache-Control": "no-store"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    # Optional separate dashboard credential; never echo or log it.
    token = os.environ.get("AERONEXUS_STATUS_TOKEN", "")
    if token:
        headers["Authorization"] = "Bearer " + token
    req = request.Request(ORIGIN + path, data=body, headers=headers, method=method)
    try:
        with opener.open(req, timeout=12) as response:
            if response.status != 200:
                raise LiveSmokeError("Unexpected HTTP status " + str(response.status))
            raw = response.read(MAX_REPLY_BYTES + 1)
            if len(raw) > MAX_REPLY_BYTES:
                raise LiveSmokeError("HTTP response exceeds safe size")
            if path == "/studio":
                if b"Mission Studio" not in raw:
                    raise LiveSmokeError("Studio HTML title missing")
                return {"ready": True}
            return json.loads(raw)
    except error.HTTPError as exc:
        # Do not include request bodies, URLs or sensitive API response details.
        raise LiveSmokeError("HTTP " + str(exc.code) + " for " + path) from None
    except (error.URLError, ssl.SSLError, TimeoutError, ValueError, json.JSONDecodeError):
        raise LiveSmokeError("HTTPS request failed for " + path) from None


def choose_polygon(objects: list[dict], index: int):
    polygons = [
        item for item in objects
        if isinstance(item, dict) and isinstance(item.get("object"), dict)
        and item["object"].get("kind") == "polygon"
    ]
    if not 0 <= index < len(polygons):
        raise LiveSmokeError(
            "No saved polygon at that index; select an existing polygon in Geo & Gelände")
    return polygons[index], len(polygons)


def validate_preview(data: dict, polygon: dict) -> tuple[int, float]:
    if not isinstance(data, dict) or data.get("kind") != "survey-preview":
        raise LiveSmokeError("Unexpected survey preview result kind")
    count, length, legs = data.get("leg_count"), data.get("distance_m"), data.get("legs")
    if (not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 200
            or not isinstance(legs, list) or len(legs) != count
            or not isinstance(length, (float, int)) or isinstance(length, bool)
            or not math.isfinite(length) or length <= 0):
        raise LiveSmokeError("Invalid survey preview metrics")
    vertices = polygon["vertices"]
    lat_min = min(p["latitude"] for p in vertices) - 0.00002
    lat_max = max(p["latitude"] for p in vertices) + 0.00002
    lon_min = min(p["longitude"] for p in vertices) - 0.00002
    lon_max = max(p["longitude"] for p in vertices) + 0.00002
    for leg in legs:
        if not isinstance(leg, list) or len(leg) != 2:
            raise LiveSmokeError("Invalid preview segment")
        for point in leg:
            if not isinstance(point, dict):
                raise LiveSmokeError("Invalid preview point")
            lat, lon = point.get("latitude"), point.get("longitude")
            if (not isinstance(lat, (float, int)) or not isinstance(lon, (float, int))
                    or isinstance(lat, bool) or isinstance(lon, bool)
                    or not math.isfinite(lat) or not math.isfinite(lon)
                    or not lat_min <= lat <= lat_max or not lon_min <= lon <= lon_max):
                raise LiveSmokeError("Preview point outside polygon bounds")
    if "waypoints" in data or "flight_commands" in data:
        raise LiveSmokeError("Survey preview unexpectedly returned execution data")
    return count, float(length)


def server_spki_hash(ca: Path) -> str:
    cert = ca.parent / "server.crt"
    if not cert.is_file():
        raise LiveSmokeError("Expected server.crt next to ca.crt for Chromium")
    try:
        pub = subprocess.run(
            ["openssl", "x509", "-in", str(cert), "-pubkey", "-noout"],
            check=True, capture_output=True, timeout=8).stdout
        spki = subprocess.run(
            ["openssl", "pkey", "-pubin", "-outform", "DER"],
            input=pub, check=True, capture_output=True, timeout=8).stdout
        return base64.b64encode(hashlib.sha256(spki).digest()).decode("ascii")
    except (OSError, subprocess.SubprocessError):
        raise LiveSmokeError("Could not obtain local server SPKI hash") from None


def check_browser(ca: Path, chosen: dict, expected_count: int,
                  spacing: float, bearing: float, screenshot: Path):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise LiveSmokeError(
            "Playwright Python module missing; install project optional [ui-browser]") from None
    chromium_path = os.environ.get("AERONEXUS_CHROMIUM_BIN", "/usr/bin/chromium")
    if not Path(chromium_path).is_file():
        raise LiveSmokeError("Chromium executable missing")
    spki = server_spki_hash(ca)
    blocked = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=chromium_path, headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage",
                  "--ignore-certificate-errors-spki-list=" + spki])
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900},
                                    ignore_https_errors=False)
            # UI must only read data, plus the documented non-persisting preview.
            def allow_only_read_and_preview(route):
                req = route.request
                if req.method in ("GET", "HEAD", "OPTIONS"):
                    route.continue_()
                elif (req.method == "POST"
                      and req.url == ORIGIN + "/api/v1/studio/survey/preview"):
                    route.continue_()
                else:
                    blocked.append(req.method)
                    route.abort()
            page.route("**/*", allow_only_read_and_preview)
            page.goto(ORIGIN + "/studio", wait_until="domcontentloaded", timeout=20000)
            page.locator('nav button[data-tab="geo-pane"]').click()
            page.locator("#survey-object option").last.wait_for(timeout=12000)
            page.locator("#survey-object").select_option(chosen["id"], timeout=12000)
            page.locator("#survey-spacing").fill(str(spacing))
            page.locator("#survey-bearing").fill(str(bearing))
            page.locator("#survey-generate").click()
            page.wait_for_function(
                """expected => {
                     const el=document.querySelector('#survey-message');
                     return !!el && el.textContent.includes(
                       expected + ' getrennte Flugstreifen');
                   }""", arg=expected_count, timeout=15000)
            vector_count = page.evaluate(
                "() => surveyLayer && surveyLayer.getLayers().length")
            if vector_count != expected_count:
                raise LiveSmokeError("Chromium Leaflet overlay count mismatch")
            svg_count = page.locator(
                "#map .leaflet-overlay-pane svg path[stroke='#ffab70']").count()
            if svg_count != expected_count:
                raise LiveSmokeError("Chromium SVG survey geometry mismatch")
            if blocked:
                raise LiveSmokeError("Unexpected mutating UI request was blocked")
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshot), full_page=False, timeout=12000)
        finally:
            browser.close()
    print("Chromium: PASS (live Leaflet flight strips, no persisted writes)")
    print("Screenshot saved locally:", screenshot)


def run(args):
    opener = build_opener(args.ca)
    health = call_api(opener, "GET", "/health")
    if health.get("status") != "ok":
        raise LiveSmokeError("Unexpected health response")
    call_api(opener, "GET", "/studio")
    objects = call_api(opener, "GET", "/api/v1/studio/geo-objects")
    if not isinstance(objects, dict) or not isinstance(objects.get("objects"), list):
        raise LiveSmokeError("Invalid geo-object response")
    chosen, count = choose_polygon(objects["objects"], args.index)
    payload = {"polygon": chosen["object"], "spacing_m": args.spacing,
               "bearing_deg": args.bearing}
    preview = call_api(opener, "POST", "/api/v1/studio/survey/preview", payload)
    legs, meters = validate_preview(preview, chosen["object"])
    print("HTTPS: PASS (verified local CA)")
    print("Saved polygons available:", count)
    print("Survey preview: PASS")
    print("Flight strips:", legs)
    print("Independent strip length:", round(meters, 1), "m")
    print("No flight commands or mission writes.")
    if args.browser:
        check_browser(args.ca, chosen, legs, args.spacing,
                      args.bearing, args.screenshot)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ca", required=True, type=Path,
                        help="Verified deployed config/pki/ca.crt")
    parser.add_argument("--index", type=int, default=0,
                        help="Zero-based index among saved polygons (default: first)")
    parser.add_argument("--spacing", type=float, default=20.0)
    parser.add_argument("--bearing", type=float, default=0.0)
    parser.add_argument("--browser", action="store_true",
                        help="Also drive real live Leaflet through Chromium/Playwright")
    parser.add_argument("--screenshot", type=Path,
                        default=Path("/tmp/aeronexus-studio-survey-live.png"))
    args = parser.parse_args(argv)
    if not math.isfinite(args.spacing) or not 2 <= args.spacing <= 200:
        parser.error("--spacing must be between 2 and 200 metres")
    if not math.isfinite(args.bearing) or not 0 <= args.bearing < 360:
        parser.error("--bearing must be in [0, 360)")
    try:
        run(args)
    except LiveSmokeError as exc:
        print("FAIL:", exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
