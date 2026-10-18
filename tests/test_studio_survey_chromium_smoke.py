"""Real Chromium acceptance for synthetic Leaflet survey interaction.

The harness runs original Studio HTML/JS offline with a deterministic Leaflet
API double. It is not a visual, tile-rendering or on-Pi acceptance test.
"""
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pi/studio_survey_chromium_smoke.py"
spec = importlib.util.spec_from_file_location("studio_survey_chromium", SCRIPT)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def test_fixture_keeps_real_studio_logic_and_isolates_external_services():
    fixture = smoke.build_fixture()
    assert "function surveyPreview()" in fixture
    assert 'id="geo-draw"' in fixture
    assert 'id="geo-save"' in fixture
    assert 'id="survey-generate"' in fixture
    assert "window.__fakeMap" in fixture
    assert "window.__surveyCalls" in fixture
    assert "No write permitted in offline UI acceptance" not in fixture
    assert "Non-readonly UI request prevented" in fixture
    assert 'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js' not in fixture
    assert 'data-survey-ui' in fixture
    assert "/api/v1/flight/command" not in fixture


@pytest.mark.parametrize("width,height", [(1440, 900), (420, 860)],
                         ids=["desktop", "mobile"])
def test_chromium_synthetic_leaflet_workflow_when_available(width, height):
    if not smoke.base.browser_binary():
        pytest.skip("Chromium unavailable; run on machine with Chromium installed")
    state, message = smoke.run_smoke(width=width, height=height)
    assert state == "pass", message
