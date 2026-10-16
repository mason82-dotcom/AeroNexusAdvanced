"""Studio HTTP API authorization and offline-only mission/media workflows."""
from io import BytesIO
from zipfile import ZipFile
import json

import pytest
from fastapi.testclient import TestClient

from aeronexus.app import app


TOKEN = "aeronexus-studio-test-token-that-is-not-a-dji-token"
HEADERS = {"Authorization": "Bearer " + TOKEN}
WAYPOINT_MISSION = {
    "name": "Dachinspektion",
    "drone_model": "matrice4t",
    "altitude_m": 42.0,
    "speed_mps": 4.0,
    "takeoff_security_height_m": 20.0,
    "rth_height_m": 60.0,
    "finish_action": "goHome",
    "waypoints": [
        {"latitude": 49.17, "longitude": 8.51, "take_photo": True},
        {"latitude": 49.18, "longitude": 8.52, "take_photo": False},
    ],
}


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    monkeypatch.setenv("AERONEXUS_WORKSPACE_DIR", str(tmp_path / "workspace"))
    with TestClient(app) as client:
        yield client, tmp_path / "workspace"


def test_studio_html_is_public_shell_but_not_private_data(api):
    client, root = api
    response = client.get("/studio")
    assert response.status_code == 200
    assert "Mission Studio" in response.text
    assert "Leaflet" not in response.text or "leaflet" in response.text.lower()
    assert TOKEN not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert not root.exists()  # static view cannot read or initialize private files


@pytest.mark.parametrize("method,url,body", [
    ("GET", "/api/v1/studio/missions", None),
    ("POST", "/api/v1/studio/missions", WAYPOINT_MISSION),
    ("GET", "/api/v1/studio/media", None),
    ("POST", "/api/v1/studio/media", None),
    ("GET", "/api/v1/studio/missions/00000000-0000-4000-8000-000000000000/export.kmz", None),
])
def test_workspace_requires_separate_token(api, method, url, body):
    client, root = api
    response = client.request(method, url, json=body)
    assert response.status_code in (401, 503)
    assert not root.exists()


def test_create_update_export_and_delete_waypoint_mission(api):
    client, root = api
    added = client.post("/api/v1/studio/missions", json=WAYPOINT_MISSION, headers=HEADERS)
    assert added.status_code == 201, added.text
    mission_id = added.json()["id"]
    assert added.json()["mission"]["name"] == WAYPOINT_MISSION["name"]
    listed = client.get("/api/v1/studio/missions", headers=HEADERS)
    assert listed.status_code == 200
    assert listed.json()["missions"][0]["id"] == mission_id
    mission = client.get("/api/v1/studio/missions/" + mission_id, headers=HEADERS)
    assert mission.json()["mission"]["waypoints"][0]["take_photo"] is True
    modified = {**WAYPOINT_MISSION, "name": "Geändert"}
    updated = client.put("/api/v1/studio/missions/" + mission_id,
                         json=modified, headers=HEADERS)
    assert updated.status_code == 200
    assert updated.json()["mission"]["name"] == "Geändert"
    downloaded = client.get("/api/v1/studio/missions/" + mission_id + "/export.kmz",
                            headers=HEADERS)
    assert downloaded.status_code == 200, downloaded.text[:200]
    assert downloaded.headers["cache-control"] == "no-store"
    assert downloaded.content[:2] == b"PK"
    with ZipFile(BytesIO(downloaded.content)) as kmz:
        assert set(kmz.namelist()) == {"wpmz/template.kml", "wpmz/waylines.wpml"}
        assert b"99" in kmz.read("wpmz/template.kml")
    assert client.delete("/api/v1/studio/missions/" + mission_id, headers=HEADERS).status_code == 204
    assert client.get("/api/v1/studio/missions/" + mission_id, headers=HEADERS).status_code == 404
    assert root.is_dir()


def test_incomplete_waypoint_mission_not_exported(api):
    client, _ = api
    mission = {**WAYPOINT_MISSION, "waypoints": [WAYPOINT_MISSION["waypoints"][0]]}
    added = client.post("/api/v1/studio/missions", json=mission, headers=HEADERS)
    assert added.status_code == 201
    result = client.get("/api/v1/studio/missions/" + added.json()["id"] + "/export.kmz",
                        headers=HEADERS)
    assert result.status_code == 422


def test_invalid_mission_schema_rejected(api):
    client, _ = api
    invalid = {**WAYPOINT_MISSION, "flight_command": "takeoff"}
    result = client.post("/api/v1/studio/missions", json=invalid, headers=HEADERS)
    assert result.status_code == 422
    assert client.get("/api/v1/studio/missions", headers=HEADERS).json()["missions"] == []


def test_media_upload_download_and_delete(api):
    client, _ = api
    binary = b"\x89PNG\r\n\x1a\n" + b"not-a-real-picture"
    response = client.post("/api/v1/studio/media", content=binary,
                           headers={**HEADERS, "Content-Type": "image/png",
                                    "X-Filename": "test%20thermal.png"})
    assert response.status_code == 201, response.text
    meta = response.json()
    assert meta["name"] == "test thermal.png"
    lst = client.get("/api/v1/studio/media", headers=HEADERS)
    assert lst.status_code == 200 and len(lst.json()["media"]) == 1
    path = "/api/v1/studio/media/" + meta["id"] + "/file"
    assert client.get(path).status_code == 401
    file = client.get(path, headers=HEADERS)
    assert file.status_code == 200 and file.content == binary
    assert file.headers["content-type"] == "image/png"
    assert file.headers["cache-control"] == "no-store"
    assert client.delete("/api/v1/studio/media/" + meta["id"], headers=HEADERS).status_code == 204
    assert client.get(path, headers=HEADERS).status_code == 404


def test_media_invalid_magic_and_type_rejected(api):
    client, _ = api
    for mime, content in (("text/html", b"<script>"), ("image/png", b"BAD")):
        response = client.post("/api/v1/studio/media", content=content,
                               headers={**HEADERS, "Content-Type": mime,
                                        "X-Filename": "a.png"})
        assert response.status_code in (400, 415)
    assert client.get("/api/v1/studio/media", headers=HEADERS).json()["media"] == []


def test_dji_flight_commands_remain_forbidden(api):
    client, _ = api
    assert client.post("/api/v1/flight/command", headers=HEADERS).status_code == 403


def test_import_own_wpml_mission_and_edit_it(api):
    client, _ = api
    first = client.post("/api/v1/studio/missions", json=WAYPOINT_MISSION, headers=HEADERS)
    assert first.status_code == 201
    src_id = first.json()["id"]
    exported = client.get(
        "/api/v1/studio/missions/" + src_id + "/export.kmz", headers=HEADERS)
    assert exported.status_code == 200
    restored = client.post(
        "/api/v1/studio/missions/import.kmz", content=exported.content,
        headers={**HEADERS, "Content-Type": "application/vnd.google-earth.kmz"})
    assert restored.status_code == 201, restored.text
    assert restored.json()["id"] != src_id
    assert restored.json()["mission"]["waypoints"] == first.json()["mission"]["waypoints"]
    assert restored.json()["mission"]["drone_model"] == "matrice4t"
    assert len(client.get("/api/v1/studio/missions", headers=HEADERS).json()["missions"]) == 2


def test_import_rejects_non_kmz_and_requires_auth(api):
    client, _ = api
    path = "/api/v1/studio/missions/import.kmz"
    assert client.post(path, content=b"Not-a-KMZ").status_code == 401
    response = client.post(path, content=b"Not-a-KMZ", headers=HEADERS)
    assert response.status_code == 422
    assert client.get("/api/v1/studio/missions", headers=HEADERS).json()["missions"] == []


def test_closed_route_persists_and_reimports_with_real_return_flight_leg(api):
    client, _ = api
    draft = {
        **WAYPOINT_MISSION,
        "close_route": True,
        "waypoints": [
            *WAYPOINT_MISSION["waypoints"],
            {"latitude": 49.181, "longitude": 8.54},
            {"latitude": 49.182, "longitude": 8.55},
        ],
    }
    created = client.post("/api/v1/studio/missions", json=draft, headers=HEADERS)
    assert created.status_code == 201, created.text
    mission_id = created.json()["id"]
    assert created.json()["mission"]["close_route"] is True
    assert created.json()["mission"]["waypoints"] == draft["waypoints"]
    saved = client.get("/api/v1/studio/missions/" + mission_id, headers=HEADERS)
    assert saved.status_code == 200
    assert saved.json()["mission"]["close_route"] is True

    exported = client.get(
        "/api/v1/studio/missions/" + mission_id + "/export.kmz", headers=HEADERS)
    assert exported.status_code == 200, exported.text[:100]
    with ZipFile(BytesIO(exported.content)) as archive:
        template = archive.read("wpmz/template.kml")
        executed = archive.read("wpmz/waylines.wpml")
    assert template.count(b"<Placemark>") == 5
    assert executed.count(b"<Placemark>") == 5
    assert b"<wpml:finishAction>goHome</wpml:finishAction>" in executed

    reimported = client.post(
        "/api/v1/studio/missions/import.kmz",
        content=exported.content,
        headers={**HEADERS, "Content-Type": "application/vnd.google-earth.kmz"},
    )
    assert reimported.status_code == 201, reimported.text
    assert reimported.json()["mission"]["close_route"] is True
    assert reimported.json()["mission"]["waypoints"] == draft["waypoints"]

    # Turning the option off must remove only the added return waypoint,
    # never change a finishAction (RTH) configuration.
    open_draft = {**reimported.json()["mission"], "close_route": False}
    response = client.put(
        "/api/v1/studio/missions/" + reimported.json()["id"],
        json=open_draft, headers=HEADERS)
    assert response.status_code == 200
    open_export = client.get(
        "/api/v1/studio/missions/" + reimported.json()["id"] + "/export.kmz",
        headers=HEADERS)
    with ZipFile(BytesIO(open_export.content)) as archive:
        assert archive.read("wpmz/waylines.wpml").count(b"<Placemark>") == 4
