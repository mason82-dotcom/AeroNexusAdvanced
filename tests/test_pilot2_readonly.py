"""Official DJI Pilot-to-Cloud GET contract, bounded metadata and viewer security."""
import asyncio
import json
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from aeronexus import pilot2_readonly as p2
from aeronexus.app import app
from aeronexus.local_waylines import Credentials, LocalWaylineError

WS = "12345678-1234-4234-8234-123456789012"
CREDS = Credentials(WS, "test-pilot-session-with-adequate-length")
UID = str(UUID(int=1))


def _get(callback, response):
    return asyncio.run(callback(CREDS, transport=httpx.MockTransport(
        lambda request: response(request) if callable(response) else response)))


def _feature(kind="Point", coords=None):
    return {"id": UID, "name": "<script>alert(1)</script>", "resource": {
        "user_name": "private person", "content": {
            "type": "Feature", "properties": {"url": "https://secret.invalid"},
            "geometry": {"type": kind, "coordinates": [-8.4, 47.2, 12] if coords is None else coords}}}}


def test_map_read_only_fixed_origin_and_allowlisted_metadata():
    def handle(req):
        assert req.method == "GET"
        assert str(req.url) == p2.ORIGIN + "/map/api/v1/workspaces/" + WS + "/element-groups"
        assert req.headers["x-auth-token"] == CREDS.access_token
        return httpx.Response(200, json={"code": 0, "data": [
            {"id": UID, "name": "Testgruppe", "type": 1, "is_lock": False,
             "elements": [_feature(), _feature("GeometryCollection")]}]})
    result = _get(p2.read_map_elements, handle)
    assert result["complete"] is True and result["crs"] == "EPSG:4326"
    assert len(result["features"]) == 1 and result["skipped_unsupported"] == 1
    assert result["features"][0]["geometry"] == {"type": "Point", "coordinates": [-8.4, 47.2, 12]}
    as_text = json.dumps(result)
    assert "private person" not in as_text and "secret.invalid" not in as_text
    assert "properties" not in as_text and CREDS.access_token not in as_text


def test_map_polygons_reject_invalid_and_excessive_coordinates():
    valid = [[[-4, 40], [-3, 40], [-3, 41], [-4, 40]]]
    assert p2._geometry({"type": "Polygon", "coordinates": valid}) is not None
    assert p2._geometry({"type": "Polygon", "coordinates": [[[-4, 40], [-3, 40], [-3, 41], [-4, 41]]]}) is None
    assert p2._geometry({"type": "Point", "coordinates": [181, 90]}) is None
    assert p2._geometry({"type": "Point", "coordinates": [float("nan"), 12]}) is None
    assert p2._geometry({"type": "LineString", "coordinates": [[0, 0]]}) is None
    assert p2._geometry({"type": "LineString", "coordinates": [[0, 0]] * 5001}) is None


def test_topology_devices_and_relationships_private_fields_removed():
    def handler(request):
        assert request.method == "GET"
        assert str(request.url) == p2.ORIGIN + "/manage/api/v1/workspaces/" + WS + "/devices/topologies"
        device = lambda sn: {"sn": sn, "device_model": {"key": "0-99-1"}, "online_status": True,
                             "device_callsign": "Matrice", "user_id": "SECRET", "icon_urls": {"normal": "secret"}}
        return httpx.Response(200, json={"code": 0, "data": {"list": [
            {"hosts": [device("aircraft-1")], "parents": [device("controller-1")]}]}})
    result = _get(p2.read_device_topology, handler)
    assert len(result["devices"]) == 2
    assert result["links"] == [{"controller_sn": "controller-1", "aircraft_sn": "aircraft-1"}]
    assert result["devices"][0]["role"] == "aircraft"
    assert "SECRET" not in json.dumps(result)
    assert "icon_urls" not in json.dumps(result)


@pytest.mark.parametrize("response,error", [
    (httpx.Response(302, headers={"location": "https://external.invalid"}), "upstream_error"),
    (httpx.Response(401, text="secret"), "authentication_required"),
    (httpx.Response(200, json={"code": -1, "message": "secret"}), "business_error"),
    (httpx.Response(200, json={"code": 0, "data": {}}), "invalid_response"),
    (httpx.Response(200, content=b"x" * (p2.MAX_BODY + 1)), "invalid_response"),
])
def test_bad_upstream_never_triggers_redirect_or_silent_empty(response, error):
    with pytest.raises(LocalWaylineError, match="^" + error + "$"):
        _get(p2.read_map_elements, response)


def test_reader_distinguishes_not_configured_and_business_error(tmp_path, monkeypatch):
    monkeypatch.setenv("AERONEXUS_LOCAL_WAYLINES_FILE", str(tmp_path / "missing.json"))
    reader = p2.Pilot2ReadOnlyReader()
    assert asyncio.run(reader.map_elements())["state"] == "not_configured"


def test_endpoints_require_viewer_access_before_local_cloud_calls(monkeypatch):
    token = "pilot-readonly-viewer-token-1234567890123"
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", token)
    seen = []
    async def map_elements(self):
        seen.append("map")
        return {"state": "connected", "groups": [], "features": [], "crs": "EPSG:4326"}
    async def topology(self):
        seen.append("topology")
        return {"state": "connected", "devices": [], "links": []}
    monkeypatch.setattr(p2.Pilot2ReadOnlyReader, "map_elements", map_elements)
    monkeypatch.setattr(p2.Pilot2ReadOnlyReader, "device_topology", topology)
    with TestClient(app) as client:
        for endpoint in ("/api/v1/local-cloud/map-elements", "/api/v1/local-cloud/topology"):
            assert client.get(endpoint).status_code == 401
        assert seen == []
        for endpoint in ("/api/v1/local-cloud/map-elements", "/api/v1/local-cloud/topology"):
            response = client.get(endpoint, headers={"Authorization": "Bearer " + token})
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
        assert seen == ["map", "topology"]
        assert client.post("/api/v1/flight/command", headers={"Authorization": "Bearer " + token}).status_code == 403


def test_diagnostics_only_get_and_keep_business_codes_not_messages():
    names = []
    def handler(request):
        assert request.method == "GET"
        assert str(request.url).startswith(p2.ORIGIN + "/")
        assert request.headers["x-auth-token"] == CREDS.access_token
        names.append(request.url.path)
        return httpx.Response(200, json={"code": -1, "message": "secret internal error",
                                          "data": {"secret": "private"}})
    result = _get(p2.read_diagnostics, handler)
    assert len(names) == 4 and len(set(names)) == 4
    assert result["all_ok"] is False
    assert result["checks"]["waylines"] == {
        "http_status": 200, "api_code": -1, "state": "business_error"}
    assert "secret" not in json.dumps(result)


def test_diagnostics_invalid_response_is_not_ok():
    result = _get(p2.read_diagnostics, httpx.Response(200, text="not-json"))
    assert result["all_ok"] is False
    assert all(value["state"] == "invalid_response" for value in result["checks"].values())
