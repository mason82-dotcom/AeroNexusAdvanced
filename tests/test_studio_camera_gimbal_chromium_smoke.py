"""Check the isolated real-Chromium camera/gimbal Studio test harness."""
import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts/pi/studio_camera_gimbal_chromium_smoke.py"
spec = importlib.util.spec_from_file_location("camera_chromium_smoke", PATH)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def test_fixture_embeds_exact_studio_action_handlers_without_network():
    text = smoke.build_fixture()
    assert 'id="point-action-list"' in text
    assert 'id="point-action-add"' in text
    assert "function addWaypointAction()" in text
    assert "function drawWaypointActions(point)" in text
    assert "function actionControls()" in text
    assert "mission.waypoints[selected]={...p," in text
    assert "document.documentElement.setAttribute('data-camera-browser-smoke','PASS')" in text
    assert "method:'POST'" not in text
    assert "fetch(" not in text
    assert "mqtt" not in text.lower()
    assert "window.open(" not in text


def test_browser_fixture_does_not_autowrite_or_require_dji_session():
    source = smoke.build_fixture()
    assert "AERONEXUS_STATUS_TOKEN" not in source
    assert "sessionStorage" not in source
    assert "localStorage" not in source
    assert "XMLHttpRequest" not in source
    assert "WebSocket(" not in source


def test_actual_chromium_camera_gimbal_dom_when_available():
    if smoke.browser_binary() is None:
        pytest.skip("Chromium not installed; Pi smoke script can be run manually")
    assert smoke.run_smoke() == 0
