#!/usr/bin/env python3
"""Read-only, real Chromium acceptance against the deployed AeroNexus HTTPS UI.

The preflight uses Python's verified-CA TLS client. Chromium gets the same CA
in a *temporary* NSS trust store, never --ignore-certificate-errors. Browser
traffic is fail-closed to whitelisted same-origin GETs, Leaflet assets and,
optionally, externally hosted map tiles; bearer tokens are only attached to
same-origin API requests. Browser responses, screenshots, filenames, GPS,
device identifiers and console messages are never printed or persisted.

The audit is NOT a DJI flight, WebRTC, full-media-decoding, or mission-write test.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import ipaddress
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.parse import urlsplit

# Executed both as a direct Pi script and imported by isolated pytest.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from production_ui_readonly_audit import (
    HTML_CHECKS, ReadOnlyClient, configured_client,
)

# The exact seven UI routes and safe single-action controls.
PAGES = (
    ("studio", "/studio", "#point-action-add"),
    ("status", "/status", "#devices"),
    ("operations", "/operations", "#refresh-now"),
    ("media", "/media", "#media-rows"),
    ("thermal", "/thermal", "#tab-flights"),
    ("multispectral", "/multispectral", "#layer"),
    ("results", "/results", "#controls"),
)
SIZES = (("Desktop", 1440, 900), ("Mobile", 420, 860))
LEAFLET_ASSETS = "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/"
TILE_ORIGINS = frozenset((
    "https://tile.openstreetmap.org",
    "https://server.arcgisonline.com",
))
# Safe clicks only, never export, upload, analysis, mission modification or scan.
SAFE_ACTIONS = {
    "studio": ("#map-tools-toggle",),
    "status": (),
    "operations": ("#tasks-finished", "#tasks-all"),
    "media": ("#refresh",),
    "thermal": ("#tab-flights", "#tab-images"),
    "multispectral": ("#view-map", "#view-image"),
    "results": ("#clear",),
}
# No text, URLs, file names or headers may appear in results.
@dataclass(frozen=True)
class Result:
    module: str
    viewport: str
    status: str
    reason: str
    api_ok: int = 0
    overflow_px: int = 0
    tile_ok: int = 0


def allow_request(url: str, method: str, base: str, *, tiles: bool = False) -> str:
    """Return narrow traffic class or 'block'. Called before every request."""
    if method != "GET":
        return "block"
    parsed = urlsplit(url)
    if parsed.username or parsed.password or parsed.fragment:
        return "block"
    if parsed.scheme != "https":
        return "block"
    base_url = urlsplit(base)
    if (parsed.hostname == base_url.hostname and parsed.port == base_url.port
            and parsed.scheme == base_url.scheme):
        if parsed.path in {p for p, _ in HTML_CHECKS}:
            return "page"
        if parsed.path.startswith("/api/v1/"):
            # No binary/large downloads, WHEP or dynamic file streams.
            if ("/file" in parsed.path or "/download" in parsed.path or
                    "/tiles/" in parsed.path or "/stack.tif" in parsed.path or
                    "/export" in parsed.path or "/temperatures" in parsed.path or
                    "/grid" in parsed.path):
                return "block"
            return "api"
        return "block"
    if url.startswith(LEAFLET_ASSETS) and parsed.path.endswith((".js", ".css", ".png", ".svg")):
        return "leaflet"
    if tiles and f"{parsed.scheme}://{parsed.netloc}" in TILE_ORIGINS:
        # Restrict to tile paths; never allow arbitrary third-party URLs.
        if (parsed.hostname == "tile.openstreetmap.org"
                and parsed.path.endswith(".png")
                and parsed.path.count("/") == 3):
            return "tile"
        if (parsed.hostname == "server.arcgisonline.com"
                and parsed.path.startswith("/ArcGIS/rest/services/World_Imagery/MapServer/tile/")):
            return "tile"
    return "block"


MAX_BROWSER_API_BYTES = 2_000_000


def relay_live_api(route, client: ReadOnlyClient) -> None:
    """A real verified-CA GET relay: bearer tokens NEVER enter Chromium.

    Avoid route.continue_(headers={Authorization:...} because redirected
    requests can inherit override headers outside the trusted origin.
    """
    parsed = urlsplit(route.request.url)
    relative = parsed.path + (("?" + parsed.query) if parsed.query else "")
    try:
        status, mime, body, excess = client._read_reviewed(
            relative, max_bytes=MAX_BROWSER_API_BYTES
        )
        if excess:
            route.fulfill(status=413, content_type="application/json",
                          body='{"detail":"Read-only browser response size limit"}')
        elif status >= 400:
            route.fulfill(status=status, content_type="application/json", body="{}")
        elif "application/json" not in mime.lower():
            route.fulfill(status=502, content_type="application/json", body="{}")
        else:
            route.fulfill(status=status, content_type="application/json", body=body)
    except Exception:
        # Never log exception text; upstream exceptions can contain object keys.
        route.fulfill(status=503, content_type="application/json", body="{}")


def browser_path() -> str | None:
    selected = os.getenv("AERONEXUS_CHROMIUM_BIN", "").strip()
    if selected:
        return shutil.which(selected)
    return next((r for x in ("chromium", "chromium-browser", "google-chrome",
                             "google-chrome-stable") if (r := shutil.which(x))), None)


def private_browser_home(home: Path, ca: Path) -> dict[str, str]:
    """Make an ephemeral NSS database; never touch the user's ~/.pki store."""
    certutil = shutil.which("certutil")
    if certutil is None:
        raise RuntimeError("certutil_missing")
    home.mkdir(mode=0o700)
    db = home / ".pki" / "nssdb"
    db.mkdir(parents=True, mode=0o700)
    subprocess.run([certutil, "-N", "-d", "sql:" + str(db), "--empty-password"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   timeout=10)
    subprocess.run([certutil, "-A", "-d", "sql:" + str(db),
                    "-n", "AeroNexus read-only audit CA", "-t", "C,,",
                    "-i", str(ca)], check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=10)
    # HOME also changes the NSS trust location; no global CA installation.
    return {**os.environ, "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_CACHE_HOME": str(home / ".cache")}


READONLY_SCRIPT = r"""(() => {
    const fetchOriginal=window.fetch.bind(window);
    window.fetch=(resource,opts={})=>{
        const method=String(opts.method||resource?.method||'GET').toUpperCase();
        if(method!=='GET')return Promise.reject(new Error('Read-only audit blocks writes'));
        return fetchOriginal(resource,opts);
    };
    const originalOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(method,...args){
        if(String(method).toUpperCase()!=='GET')throw Error('Read-only audit blocks XHR writes');
        return originalOpen.call(this,method,...args);
    };
    navigator.sendBeacon=()=>false;
    document.addEventListener('submit',event=>event.preventDefault(),true);
    HTMLFormElement.prototype.submit=function(){};
    // Studio events are deliberately not a live-data/WebSocket test.
    window.WebSocket=class ReadOnlySocket {
        constructor(){this.readyState=3;queueMicrotask(()=>this.onclose?.({code:1000}));}
        send(){throw Error('Read-only audit blocks socket writes')}
        close(){}
    };
})();"""


def evaluate_layout(page, selector: str) -> tuple[bool, int, int]:
    """Derived counts ONLY. Never return DOM text or sensitive attributes."""
    info = page.evaluate("""selector=>{
       const node=document.querySelector(selector), root=document.documentElement;
       // Empty table bodies and placeholder panes legitimately have zero height.
       // Physical clickability is tested separately for active controls.
       const present=!!node;
       return {present, overflow:Math.max(0,root.scrollWidth-root.clientWidth),
         leaflet:typeof window.L!=='undefined',
         tiles:document.querySelectorAll('.leaflet-tile-loaded').length};
    }""", selector)
    return bool(info["present"]), int(info["overflow"]), int(info["tiles"])


def safe_ui_actions(page, module: str) -> int:
    """Physical user-like Chromium clicks; all target a reviewed GET-only action."""
    clicked = 0
    for selector in SAFE_ACTIONS[module]:
        el = page.locator(selector)
        # Raise if the control is covered, off-screen or unreachable by pointer.
        el.click(timeout=6000)
        clicked += 1
    return clicked


def preflight(client: ReadOnlyClient) -> None:
    status, _, content, oversized = client.read("/health", max_bytes=1024)
    if status != 200 or oversized:
        raise RuntimeError("verified_https_health_unavailable")
    import json
    if json.loads(content).get("status") != "ok":
        raise RuntimeError("verified_https_health_invalid")


def audit_page(browser, client: ReadOnlyClient, module: str, path: str,
               selector: str, width: int, height: int, viewport: str,
               *, allow_tiles: bool) -> Result:
    context = browser.new_context(
        viewport={"width": width, "height": height},
        is_mobile=viewport == "Mobile", has_touch=viewport == "Mobile",
        ignore_https_errors=False, accept_downloads=False,
        service_workers="block", reduced_motion="reduce",
    )
    counters: Counter[str] = Counter()
    errors = 0
    context.add_init_script(READONLY_SCRIPT)

    def route_request(route):
        request = route.request
        kind = allow_request(request.url, request.method, client.base,
                             tiles=allow_tiles)
        if kind == "block":
            counters["blocked"] += 1
            return route.abort()
        if kind == "tile":
            counters["tiles_requested"] += 1
            if counters["tiles_requested"] > 18:
                return route.abort()
        if kind == "api":
            counters["api_requested"] += 1
            return relay_live_api(route, client)
        return route.continue_()

    context.route("**/*", route_request)
    page = context.new_page()
    def page_error(_):
        nonlocal errors
        errors += 1
    page.on("pageerror", page_error)

    def response_received(response):
        kind = allow_request(response.url, response.request.method, client.base,
                             tiles=allow_tiles)
        if kind == "api" and response.status == 200:
            counters["api_ok"] += 1
        if kind == "leaflet" and response.status == 200:
            counters["leaflet_ok"] += 1
        if kind == "tile" and response.status == 200:
            counters["tile_ok"] += 1
    page.on("response", response_received)
    try:
        navigation = page.goto(client.base + path, wait_until="domcontentloaded", timeout=18000)
        if navigation is None or navigation.status != 200:
            return Result(module, viewport, "FAIL", "HTTPS page status invalid")
        page.wait_for_timeout(2200)
        present, overflow, loaded_tiles = evaluate_layout(page, selector)
        if not present:
            return Result(module, viewport, "FAIL", "expected control missing")
        if counters["api_ok"] == 0:
            return Result(module, viewport, "FAIL", "no successful real API GET")
        if errors:
            return Result(module, viewport, "FAIL", "unhandled browser JS error(s)")
        if overflow > 8:
            return Result(module, viewport, "FAIL",
                          "horizontal viewport overflow", counters["api_ok"], overflow)
        try:
            clicks = safe_ui_actions(page, module)
        except Exception:
            return Result(module, viewport, "FAIL", "safe UI control unreachable",
                          counters["api_ok"], overflow)
        page.wait_for_timeout(550)
        if errors:
            return Result(module, viewport, "FAIL", "JS error after safe interaction",
                          counters["api_ok"], overflow)
        # Leaflet assets are real where CDN is reachable; maps/tiles are optional.
        return Result(module, viewport, "PASS",
                      "real HTTPS browser, GET data, layout, safe clicks",
                      counters["api_ok"], overflow, counters["tile_ok"])
    except Exception:
        return Result(module, viewport, "FAIL",
                      "browser load/layout error", counters["api_ok"])
    finally:
        context.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only live HTTPS Chromium UI audit")
    parser.add_argument("--instance-dir", type=Path,
                        default=Path.home() / "Projekte" / "AeroNexusAdvanced")
    parser.add_argument("--allow-tiles", action="store_true",
                        help="Opt in to fetching at most 18 tiles per page from OSM/Esri")
    args = parser.parse_args(argv)
    browser = browser_path()
    if not browser:
        print("SKIP: System Chromium not installed")
        return 2
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("SKIP: Optional Python Playwright dependency missing")
        return 2

    try:
        client = configured_client(args.instance_dir.resolve())
        preflight(client)
        with tempfile.TemporaryDirectory(prefix="aeronexus-live-browser-") as folder:
            home = Path(folder) / "home"
            env = private_browser_home(home, args.instance_dir.resolve() /
                                       "config/pki/ca.crt")
            with sync_playwright() as playwright:
                chromium = playwright.chromium.launch(
                    headless=True, executable_path=browser, env=env,
                    args=["--no-sandbox", "--disable-dev-shm-usage",
                          "--disable-background-networking",
                          "--disable-component-update", "--disable-sync",
                          "--disable-extensions", "--no-proxy-server"],
                )
                try:
                    results = [
                        audit_page(chromium, client, module, path, selector,
                                   w, h, name, allow_tiles=args.allow_tiles)
                        for name, w, h in SIZES
                        for module, path, selector in PAGES
                    ]
                finally:
                    chromium.close()
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as e:
        print("FAIL: Secure browser preflight/setup (" + type(e).__name__ + ")")
        return 2
    for result in results:
        print(f"{result.status:4}  {result.module:15} {result.viewport:7} "
              f"API-200={result.api_ok} tiles-200={result.tile_ok} "
              f"overflow={result.overflow_px}px | {result.reason}")
    passed = sum(x.status == "PASS" for x in results)
    print(f"Total: {passed}/{len(results)} real HTTPS browser cases PASS")
    print("All actual writes blocked; no response body, screenshot or token persisted.")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
