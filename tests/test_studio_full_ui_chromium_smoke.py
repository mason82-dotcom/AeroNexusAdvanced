"""Full rendered Studio Chromium browser/UI coverage with no live resources."""
import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aeronexus.app import app

PATH = Path(__file__).resolve().parents[1] / "scripts/pi/studio_full_ui_chromium_smoke.py"
SPEC = importlib.util.spec_from_file_location("studio_full_ui_chromium", PATH)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


def test_entire_studio_html_is_used_with_strict_mock_get_only():
    source = smoke.build_fixture()
    assert 'data-tab="map-pane"' in source
    for page in ("geo-pane", "terrain-pane", "media-pane",
                 "waylines-pane", "fleet-pane"):
        assert 'data-tab="' + page + '"' in source
    for path in ("/operations", "/status", "/thermal",
                 "/multispectral", "/results"):
        assert 'href="' + path + '"' in source
    assert '<script src="https://cdn.jsdelivr.net/npm/leaflet' not in source
    assert "window.fetch=async function" in source
    assert "method!=='GET'" in source
    assert "method:'POST'" not in smoke.CHECKS


@pytest.mark.parametrize("path", [
    "/studio", "/status", "/operations", "/media",
    "/thermal", "/multispectral", "/results",
])
def test_other_html_views_are_reachable_via_in_process_http(path):
    response = TestClient(app).get(path)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert len(response.text) > 200
    assert response.headers.get("cache-control") == "no-store"


def test_desktop_and_mobile_full_studio_browser_when_available():
    if not smoke.browser_binary():
        pytest.skip("Chromium unavailable; run on Pi with the packaged smoke script")
    for width, height in ((1440, 900), (420, 860)):
        state, detail = smoke.run_smoke(width=width, height=height)
        assert state == "pass", detail
