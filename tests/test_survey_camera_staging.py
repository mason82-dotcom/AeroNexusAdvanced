"""Offline staging lifecycle and allowlist tests for the DJI camera browser smoke.

A subprocess integration test uses a disposable on-disk workspace and
127.0.0.1 only; no DJI creds, real user workspace, production port, or web.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
from urllib.request import Request, urlopen

import pytest


SOURCE = Path(__file__).resolve().parents[1] / "scripts/pi/studio_camera_staging_smoke.py"
SPEC = importlib.util.spec_from_file_location("studio_camera_staging", SOURCE)
staging = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(staging)
CHECKOUT = SOURCE.parents[2]


def test_staging_environment_never_inherits_dji_or_production_secrets(monkeypatch, tmp_path):
    monkeypatch.setenv("DJI_ACCESS_TOKEN", "fake-protected-token")
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", "fake-protected-token")
    monkeypatch.setenv("AERONEXUS_TLS_KEY", "/production/key")
    monkeypatch.setenv("HTTPS_PROXY", "http://example.invalid")
    env = staging.isolated_env(tmp_path / "workspace", CHECKOUT)
    assert "DJI_ACCESS_TOKEN" not in env
    assert "AERONEXUS_STATUS_TOKEN" not in env
    assert "AERONEXUS_TLS_KEY" not in env
    assert "HTTPS_PROXY" not in env
    assert env["AERONEXUS_LAN_NO_TOKEN"] == "1"
    assert env["AERONEXUS_WORKSPACE_DIR"] == str(tmp_path / "workspace")
    assert env["HOME"] == str(tmp_path / "home")
    assert env["HOME"] != os.environ.get("HOME")
    assert (tmp_path / "home").stat().st_mode & 0o077 == 0
    assert env["PYTHONPATH"] == str(CHECKOUT / "src")
    assert ".env" not in env.values()


def test_staging_workspace_contains_only_synthetic_polygon(tmp_path):
    root = tmp_path / "new-workspace"
    staging.seed_synthetic_workspace(root)
    assert root.stat().st_mode & 0o077 == 0
    assert (root / "missions").is_dir()
    assert list((root / "missions").iterdir()) == []
    files = list((root / "geo_objects").glob("*.json"))
    assert len(files) == 1
    item = json.loads(files[0].read_text(encoding="utf-8"))
    assert item["id"] == staging.TEST_ID
    assert item["object"]["kind"] == "polygon"
    assert "Synthetic" in item["object"]["name"]


@pytest.mark.parametrize(("method","url","allowed"), [
    ("GET", "http://127.0.0.1:18081/studio", True),
    ("GET", "http://127.0.0.1:18081/api/v1/studio/missions", True),
    ("POST", "http://127.0.0.1:18081/api/v1/studio/survey/preview", True),
    ("POST", "http://127.0.0.1:18081/api/v1/studio/missions", False),
    ("DELETE", "http://127.0.0.1:18081/api/v1/studio/geo-objects/foo", False),
    ("POST", "http://127.0.0.1:18081/api/v1/studio/survey/preview?unsafe=1", False),
    ("POST", "http://127.0.0.1:8000/api/v1/studio/survey/preview", False),
    ("GET", "https://server.arcgisonline.com/ArcGIS/foo", True),
    ("GET", "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js", True),
    ("POST", "https://server.arcgisonline.com/ArcGIS/foo", False),
    ("GET", "https://developer.dji.com/foo", False),
    ("GET", "http://not-a-trusted-server.invalid/", False),
])
def test_browser_request_policy(method, url, allowed):
    assert staging.browser_request_allowed(
        method, url, "http://127.0.0.1:18081") == allowed


def test_preview_validator_requires_camera_and_no_executable_route():
    base = {
        "kind": "survey-preview",
        "leg_count": 1,
        "legs": [[staging.RECTANGLE[0], staging.RECTANGLE[1]]],
        "distance_m": 20.0,
        "camera_plan": {
            "profile_id": staging.PROFILE,
            "gsd_cm_px": 1.2, "spacing_m": 25.0,
            "trigger_interval_m": 12.0
        },
    }
    assert staging.validate_result(base)[0] == 1
    for bad in ({**base, "camera_plan": {}}, {**base, "leg_count": 2},
                {**base, "flight_commands": []}):
        with pytest.raises(staging.StagingSmokeError):
            staging.validate_result(bad)


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_real_local_asgi_server_receives_camera_preview_without_workspace_write(tmp_path):
    """CI smoke: real HTTP stack, real FastAPI, synthetic polygon, no browser."""
    workspace = tmp_path / "staging"
    staging.seed_synthetic_workspace(workspace)
    port = _free_loopback_port()
    with staging.staging_server(Path(sys.executable), CHECKOUT, workspace, port) as origin:
        with urlopen(origin + "/api/v1/studio/geo-objects", timeout=5) as res:
            objects = json.load(res)
        assert objects["objects"][0]["id"] == staging.TEST_ID
        payload = {
            "polygon": objects["objects"][0]["object"],
            "spacing_m": 20,
            "bearing_deg": 0,
            "camera": {
                "profile_id": staging.PROFILE,
                "height_agl_m": 60,
                "side_overlap_pct": 70,
                "front_overlap_pct": 80,
            },
        }
        req = Request(
            origin + "/api/v1/studio/survey/preview",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "Origin": origin},
            method="POST")
        with urlopen(req, timeout=10) as res:
            assert res.status == 200
            result = json.load(res)
        count, distance, optics = staging.validate_result(result)
        assert count > 1
        assert distance > 100
        assert optics["estimated_photo_count"] > 0
        with urlopen(origin + "/api/v1/studio/missions", timeout=5) as res:
            assert json.load(res)["missions"] == []
    assert list((workspace / "missions").iterdir()) == []
    assert len(list((workspace / "geo_objects").glob("*.json"))) == 1
