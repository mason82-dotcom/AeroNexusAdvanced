"""Browser smoke for the original standalone AeroNexus HTML UIs."""
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pi/standalone_ui_chromium_smoke.py"
spec = importlib.util.spec_from_file_location("standalone_ui_chromium", SCRIPT)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


@pytest.mark.parametrize("name", tuple(smoke.PAGES))
def test_entire_html_fixture_remains_read_only_and_has_dom_probe(name):
    html = smoke.fixture(name)
    assert "window.__uiWriteAttempts" in html
    assert "window.fetch=async(path,opts={})" in html
    assert "No write permitted in offline UI acceptance" in html
    assert "window.__uiBoundClickIds" in html
    assert 'data-standalone-ui' in html
    assert 'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js' not in html


@pytest.mark.parametrize("name", tuple(smoke.PAGES))
@pytest.mark.parametrize("viewport", [(1440, 900), (420, 860)], ids=["desktop", "mobile"])
def test_real_chromium_standalone_page_when_available(name, viewport):
    if not smoke.browser_binary():
        pytest.skip("Chromium not installed; can run directly on Raspberry Pi")
    result, detail = smoke.run_module(name, width=viewport[0], height=viewport[1])
    assert result == "pass", detail
