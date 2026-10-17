"""Metadata hints cannot establish route identity or flight execution."""
import json

import pytest
from fastapi.testclient import TestClient

from aeronexus.app import app
from aeronexus.mission_reconciliation import compare_missions
from aeronexus.providers import ProviderKind
from aeronexus.status_runtime import StatusRuntime


LOCAL = {"id": "local-id", "name": "Dach Nord", "drone_model": "mavic3e"}
SOURCE = (ProviderKind.PUBLIC_V2, "project-a")


def cloud(**changes):
    return {"id": "cloud-id", "name": "dach  NORD", "device_model_key": "0-77-0", **changes}


@pytest.mark.parametrize("key,expected", [("0-77-0", True), ("0-77-1", False), (None, None)])
def test_name_candidates_are_project_scoped_unverified_and_model_checked(key, expected):
    report = compare_missions([LOCAL], {SOURCE: {"waylines": [cloud(device_model_key=key)], "tasks": []}}, "2026-10-17T12:00:00Z")
    row = report["missions"][0]
    assert row["status"] == "unverified_candidates"
    candidate, = row["candidates"]
    assert candidate["model_match"] is expected
    assert candidate["content_match"] is None
    assert candidate["verification"] == "name_only"
    assert candidate["project_id"] == "project-a"
    assert report["coverage"]["route_content_verified"] is False


def test_missing_unreadable_and_empty_cloud_are_distinguishable():
    missing = compare_missions([LOCAL], {}, None)
    assert missing["coverage"]["cloud_cache_available"] is False
    unreadable = compare_missions([LOCAL], {SOURCE: {"waylines": None, "tasks": None}}, None)
    assert unreadable["projects"][0]["waylines_readable"] is False
    empty = compare_missions([LOCAL], {SOURCE: {"waylines": [], "tasks": []}}, None)
    assert empty["projects"][0]["waylines_readable"] is True
    assert empty["missions"][0]["status"] == "no_candidate_in_cache"
    assert empty["coverage"]["full_inventory_verified"] is False


def test_duplicate_names_remain_ambiguous_bounded_and_project_scoped():
    catalog = {SOURCE: {"waylines": [cloud(id=str(i)) for i in range(200)], "tasks": []},
               (ProviderKind.PUBLIC_V2, "project-b"): {"waylines": [cloud()], "tasks": []}}
    report = compare_missions([LOCAL], catalog, None)
    assert report["missions"][0]["candidate_count"] == 201
    assert len(report["missions"][0]["candidates"]) == 10
    assert report["projects"][0]["waylines_at_limit"] is True


def test_no_fuzzy_identity_task_name_matching_or_sensitive_upstream_forwarding():
    report = compare_missions([LOCAL], {SOURCE: {
        "waylines": [cloud(name="Dach Nord 2", url="secret")],
        "tasks": [{"uuid": "task-id", "name": "Dach Nord", "status": "success", "url": "secret"}]}}, None)
    assert report["missions"][0]["candidates"] == []
    assert report["flight_tasks"][0]["wayline_link"] == "unavailable"
    assert "secret" not in json.dumps(report)


def test_reconciliation_api_auth_no_store_and_no_mission_changes(tmp_path, monkeypatch):
    token = "mission-report-local-test-token-123456789"
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", token)
    root = tmp_path / "workspace"
    monkeypatch.setenv("AERONEXUS_WORKSPACE_DIR", str(root))
    runtime = StatusRuntime()
    runtime.catalog[SOURCE] = {"waylines": [cloud()], "tasks": []}
    monkeypatch.setattr(app.state, "status_runtime", runtime)
    with TestClient(app) as client:
        url = "/api/v1/studio/missions/reconciliation"
        assert client.get(url).status_code == 401
        assert not root.exists()
        headers = {"Authorization": "Bearer " + token}
        saved = client.post("/api/v1/studio/missions", headers=headers,
                            json={"name": LOCAL["name"], "drone_model": "mavic3e"})
        assert saved.status_code == 201
        original = {path.name: path.read_bytes() for path in (root / "missions").glob("*.json")}
        result = client.get(url, headers=headers)
        assert result.status_code == 200
        assert result.headers["cache-control"] == "no-store"
        assert result.json()["missions"][0]["local_id"] == saved.json()["id"]
        assert result.json()["missions"][0]["candidates"][0]["wayline_id"] == "cloud-id"
        assert original == {path.name: path.read_bytes() for path in (root / "missions").glob("*.json")}


@pytest.mark.parametrize("model", ["mavic3e", "mavic3t", "mavic3m", "mavic3ta"])
def test_mavic_api_save_load_and_export_preserves_model(tmp_path, monkeypatch, model):
    from io import BytesIO
    from zipfile import ZipFile
    from aeronexus.wpml_export import import_kmz
    token = "mission-model-api-test-token-123456789"
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", token)
    monkeypatch.setenv("AERONEXUS_WORKSPACE_DIR", str(tmp_path / "workspace"))
    headers = {"Authorization": "Bearer " + token}
    mission = {"name": "Modelltest", "drone_model": model,
               "waypoints": [{"latitude": 49.0, "longitude": 8.0, "take_photo": True},
                             {"latitude": 49.001, "longitude": 8.001}]}
    with TestClient(app) as client:
        saved = client.post("/api/v1/studio/missions", json=mission, headers=headers)
        assert saved.status_code == 201
        item_id = saved.json()["id"]
        loaded = client.get("/api/v1/studio/missions/" + item_id, headers=headers)
        assert loaded.json()["mission"]["drone_model"] == model
        data = client.get("/api/v1/studio/missions/" + item_id + "/export.kmz", headers=headers)
        assert data.status_code == 200
        assert import_kmz(data.content).drone_model == model
        # Tampered files must not produce a new private workspace record.
        buffer = BytesIO()
        with ZipFile(BytesIO(data.content)) as source, ZipFile(buffer, "w") as out:
            for name in source.namelist():
                content = source.read(name)
                if name.endswith("waylines.wpml"):
                    content = content.replace(b"<wpml:waypointSpeed>5<", b"<wpml:waypointSpeed>12<")
                out.writestr(name, content)
        rejected = client.post("/api/v1/studio/missions/import.kmz", content=buffer.getvalue(), headers=headers)
        assert rejected.status_code == 422
        assert len(client.get("/api/v1/studio/missions", headers=headers).json()["missions"]) == 1
