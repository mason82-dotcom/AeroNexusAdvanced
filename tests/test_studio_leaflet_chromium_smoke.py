"""Offline Chromium acceptance with the genuine Leaflet 1.9.4 map engine.

Only inert test tiles and synthetic in-memory HTTP fixtures are available.
The executable route remains untouched; no live Pi/DJI/MinIO requests.
"""
import importlib.util
import os
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pi/studio_leaflet_chromium_smoke.py"
SPEC = importlib.util.spec_from_file_location("studio_leaflet_chromium", SCRIPT)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


def test_real_leaflet_fixture_replaces_only_external_assets_and_tiles():
    source = smoke.build_fixture()
    assert '<script src="leaflet.js"></script>' in source
    assert '<link rel="stylesheet" href="leaflet.css">' in source
    assert 'data:image/png;base64,' in source
    assert "window.__fakeMap" not in source
    assert 'L.map("map"' in source
    assert "window.__surveyCalls" in source
    assert 'data-real-leaflet-ui' in source
    assert 'https://tile.openstreetmap.org/' not in source
    assert 'https://server.arcgisonline.com/' not in source
    assert 'https://cdn.jsdelivr.net/npm/leaflet@1.9.4' not in source
    assert '/api/v1/flight/command' not in source


@pytest.mark.parametrize("width,height", [(1440, 900), (420, 860)],
                         ids=["desktop", "mobile"])
def test_genuine_leaflet_dom_geometry_in_chromium(width, height):
    if smoke.base.base.browser_binary() is None or smoke.assets_dir() is None:
        if os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
            pytest.fail("CI must supply Chromium and pinned Leaflet JS/CSS assets")
        pytest.skip("Chromium or SRI-pinned Leaflet test assets not installed locally")
    outcome, detail = smoke.run_smoke(width=width, height=height)
    assert outcome == "pass", detail
