"""Port-8085 portal: optional mount, no changes to Pilot 2 or DJI credentials."""
import importlib.util
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pi/stage_control_portal.py"
SPEC = importlib.util.spec_from_file_location("stage_control_portal", SCRIPT)
portal = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(portal)


def fixtures(tmp_path):
    edge = tmp_path / "cloud-server/edge"
    edge.mkdir(parents=True)
    (edge / "compose.core.yaml").write_text("services:\n  control:\n    image: test\n")
    (edge / "compose.brand.yaml").write_text("services:\n  control:\n    image: branded\n")
    static = tmp_path / "deploy/cloud-server/control-portal"
    static.mkdir(parents=True)
    (static / "index.html").write_text("<html>Portal</html>")
    (static / "fh2.html").write_text("<html>FlightHub</html>")
    return edge, static


def test_portal_mount_only_control_and_is_read_only(tmp_path):
    edge, static = fixtures(tmp_path)
    rendered = portal.preflight(edge, static)
    assert "  control:" in rendered
    assert "read_only: true" in rendered
    assert "create_host_path: false" in rendered
    assert "/usr/share/nginx/html/aeronexus" in rendered
    assert str(static) in rendered
    assert "api:" not in rendered and "emqx:" not in rendered
    assert "ports:" not in rendered
    assert "restart:" not in rendered


def test_staging_is_idempotent_and_refuses_modified_overlay(tmp_path):
    edge, static = fixtures(tmp_path)
    overlay = edge / "compose.portal.yaml"
    content = portal.preflight(edge, static)
    assert portal.stage(overlay, content).startswith("Overlay geschrieben")
    assert overlay.stat().st_mode & 0o777 == 0o600
    assert portal.stage(overlay, content) == "Bereits korrekt vorbereitet"
    overlay.write_text("CUSTOM LOCAL SETTINGS", encoding="utf-8")
    with pytest.raises(RuntimeError, match="nicht überschrieben"):
        portal.stage(overlay, content)


def test_preflight_requires_existing_branding_and_static_assets(tmp_path):
    edge, static = fixtures(tmp_path)
    (edge / "compose.brand.yaml").unlink()
    with pytest.raises(RuntimeError, match="Compose-Datei"):
        portal.preflight(edge, static)
    (edge / "compose.brand.yaml").write_text("ok")
    (static / "fh2.html").unlink()
    with pytest.raises(RuntimeError, match="Portaldatei"):
        portal.preflight(edge, static)


def test_default_mode_is_non_mutating(tmp_path, monkeypatch):
    edge, static = fixtures(tmp_path)
    monkeypatch.setattr(portal, "EDGE", edge)
    monkeypatch.setattr(portal, "PORTAL", static)
    monkeypatch.setattr(portal, "OVERLAY", edge / "compose.portal.yaml")
    assert portal.main([]) == 0
    assert not (edge / "compose.portal.yaml").exists()


def test_ui_is_real_navigation_without_fake_telemetry():
    html = (ROOT / "deploy/cloud-server/control-portal/index.html").read_text()
    assert 'href="/pilot-login"' in html
    assert 'data-app="status"' in html and 'data-app="operations"' in html
    assert 'data-app="studio"' in html
    assert '"https://"+host+":8000/"' in html
    assert 'fetch("/pilot-login",{method:"HEAD"' in html
    assert "localStorage" not in html and "x-user-token" not in html
    assert "DJI_APP_LICENSE" not in html


def test_fh2_opt_in_and_native_api_call_shapes():
    html = (ROOT / "deploy/cloud-server/control-portal/fh2.html").read_text()
    assert 'id="consent" type="checkbox" required' in html
    assert "window.FH2.initConfig" in html
    assert 'window.FH2.loadProject("project-app-container")' in html
    assert 'window.FH2.loadCockpit("cockpit-app-container"' in html
    assert "/paas.js" in html
    assert "localStorage.setItem" not in html
    assert "fetch(" not in html
    assert not re.search(r"eyJ[a-zA-Z0-9_-]{25,}\.", html)
    assert "loadWaylineCreation" not in html and "createFlightTask" not in html


def test_script_does_not_invoke_docker_or_touch_original_vue():
    src = SCRIPT.read_text()
    assert "subprocess" not in src
    assert "docker compose" in src
    assert "index.html" in src and "fh2.html" in src
    assert "src/locales" not in src
