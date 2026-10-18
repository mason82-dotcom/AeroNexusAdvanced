"""Safe policy and real-layout helper tests for live production browser audit."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts/pi/production_ui_browser_audit.py"
spec = importlib.util.spec_from_file_location("live_ui_browser_audit", PATH)
audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)

BASE = "https://192.168.178.63:8000"


@pytest.mark.parametrize(("url", "kind"), (
    (BASE + "/studio", "page"),
    (BASE + "/api/v1/status/devices?limit=5", "api"),
    ("https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js", "leaflet"),
    ("https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css", "leaflet"),
    ("http://192.168.178.63:8000/studio", "block"),
    ("https://192.168.178.64:8000/api/v1/status/devices", "block"),
    ("https://attacker.example/api/v1/status/devices", "block"),
    (BASE + "/api/v1/studio/dji-media/" + "a"*64 + "/file", "block"),
    (BASE + "/api/v1/results/abc/tiles/10/30/20.png", "block"),
    (BASE + "/api/v1/multispectral/captures/abc/stack.tif", "block"),
    (BASE + "/other", "block"),
    ("file:///etc/passwd", "block"),
)))
def test_exact_request_allowlist(url, kind):
    assert audit.allow_request(url, "GET", BASE) == kind


def test_write_methods_never_allowed():
    for method in ("POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
        assert audit.allow_request(BASE + "/api/v1/status/devices", method, BASE) == "block"
        assert audit.allow_request(BASE + "/studio", method, BASE) == "block"


def test_tiles_need_explicit_opt_in_and_are_bounded():
    tile = "https://tile.openstreetmap.org/13/4255/2770.png"
    assert audit.allow_request(tile, "GET", BASE) == "block"
    assert audit.allow_request(tile, "GET", BASE, tiles=True) == "tile"
    assert audit.allow_request("https://tile.openstreetmap.org/tracker",
                               "GET", BASE, tiles=True) == "block"


def test_script_blocks_dom_and_api_writes():
    assert "window.fetch" in audit.READONLY_SCRIPT
    assert "XMLHttpRequest.prototype.open" in audit.READONLY_SCRIPT
    assert "navigator.sendBeacon" in audit.READONLY_SCRIPT
    assert "HTMLFormElement.prototype.submit" in audit.READONLY_SCRIPT
    assert "window.WebSocket" in audit.READONLY_SCRIPT
    assert set(audit.SAFE_ACTIONS) == {x[0] for x in audit.PAGES}


def test_layout_check_counts_only_not_dom_text():
    class Page:
        def evaluate(self, js, selector):
            assert "textContent" not in js
            assert "innerHTML" not in js
            return {"present": True, "overflow": 5, "tiles": 0}
    assert audit.evaluate_layout(Page(), "#status") == (True, 5, 0)


def test_real_chromium_safe_clicks_with_isolated_file_fixture():
    playwright = pytest.importorskip("playwright.sync_api")
    browser = audit.browser_path()
    if not browser:
        pytest.skip("System Chromium not installed")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        driver = p.chromium.launch(headless=True, executable_path=browser,
                                   args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            page = driver.new_page(viewport={"width": 420, "height": 860})
            page.set_content("""<!doctype html><button id="tasks-finished">Finish</button>
              <button id="tasks-all">All</button><script>
              let n=0;document.querySelectorAll("button").forEach(b=>
                 b.onclick=()=>{b.dataset.clicked=String(++n)});
              </script>""")
            assert audit.safe_ui_actions(page, "operations") == 2
            assert page.locator("#tasks-all").get_attribute("data-clicked") == "2"
        finally:
            driver.close()
