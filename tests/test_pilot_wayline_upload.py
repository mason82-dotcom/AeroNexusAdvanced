"""Opt-in Pilot 2 upload: no writes unless explicitly armed, safe mocked POSTs."""
import asyncio
import json
from uuid import UUID

import httpx
import pytest

from aeronexus.local_waylines import Credentials
from aeronexus.pilot_wayline_upload import UploadError, prepare, upload
from aeronexus.studio_workspace import Workspace
from aeronexus.wpml_export import WaypointMission, Waypoint

WID = "12345678-1234-4234-8234-123456789012"
MID = "00000000-0000-0000-0000-000000000123"
CREDS = Credentials(WID, "local-session-secret-123456789")


def mission():
    return WaypointMission(
        name="Dachinspektion Probe", drone_model="mavic3m",
        waypoints=[
            Waypoint(latitude=49.1, longitude=8.4),
            Waypoint(latitude=49.1001, longitude=8.4001, take_photo=True),
        ])


class LocalStore:
    def get_mission(self, item_id):
        assert item_id == MID
        return {"mission": mission().model_dump()}


def plan():
    return prepare(MID, workspace=LocalStore(), timestamp_ms=1792250000123,
                   nonce="abcdefabcdef")


def envelope(names):
    rows = [{"id": str(UUID(int=i+1)), "name": name,
             "drone_model_key": "0-77-2", "template_types": [0],
             "update_time": 1792250000123}
            for i, name in enumerate(names)]
    return {"code": 0, "data": {"list": rows,
            "pagination": {"total": len(rows), "page": 1, "page_size": 50}}}


def handler_factory(calls, *, post_code=0, after=True, invalid_session=False,
                    network_failure=False):
    def handler(request):
        calls.append((request.method, request.url.path))
        assert request.url.host == "127.0.0.1"
        assert request.headers.get("x-auth-token") == CREDS.access_token
        if request.url.path == "/manage/api/v1/users/current":
            return httpx.Response(200, json={"code": 0, "data": {
                "workspace_id": WID, "user_type": 99 if invalid_session else 1}})
        if request.method == "GET":
            assert request.url.path == f"/wayline/api/v1/workspaces/{WID}/waylines"
            assert request.url.params["order_by"] == "create_time asc"
            uploaded = any(method == "POST" for method, _ in calls)
            return httpx.Response(200, json=envelope(
                [plan().filename[:-4]] if uploaded and after else []))
        assert request.method == "POST"
        assert request.url.path == (
            f"/wayline/api/v1/workspaces/{WID}/waylines/file/upload")
        assert b'filename="' + plan().filename.encode() + b'"' in request.content
        assert b"PK\x03\x04" in request.content  # zipped KMZ sent, not XML plaintext
        if network_failure:
            raise httpx.ReadTimeout("server could have accepted the upload")
        return httpx.Response(200, json={
            "code": post_code, "message": "PRIVATE_UPSTREAM_CONTENT"})
    return handler


def test_prepare_is_offline_and_generates_valid_kmz():
    result = plan()
    assert result.drone_model == "mavic3m"
    assert result.points == 2
    assert result.filename.endswith("abcdefabcdef.kmz")
    assert result.kmz[:2] == b"PK"
    assert "49." not in repr(result)  # coordinates hidden from logs


def test_invalid_ids_and_missions_rejected_without_io():
    with pytest.raises(UploadError, match="invalid_mission"):
        prepare("../../etc/passwd", workspace=LocalStore())
    with pytest.raises(UploadError, match="invalid_nonce"):
        prepare(MID, workspace=LocalStore(), nonce="../evil")


def test_no_post_while_disabled(monkeypatch):
    monkeypatch.delenv("AERONEXUS_PILOT_WAYLINE_UPLOAD_ENABLED", raising=False)
    calls = []
    transport = httpx.MockTransport(handler_factory(calls))
    with pytest.raises(UploadError, match="upload_disabled"):
        asyncio.run(upload(plan(), CREDS, expected_model="mavic3m", transport=transport))
    assert not calls


def test_upload_is_single_post_and_verified(monkeypatch):
    monkeypatch.setenv("AERONEXUS_PILOT_WAYLINE_UPLOAD_ENABLED", "1")
    calls = []
    result = asyncio.run(upload(
        plan(), CREDS, expected_model="mavic3m", transport=httpx.MockTransport(handler_factory(calls))))
    assert result == {"state": "registered", "name": plan().filename[:-4],
                      "verified": True}
    assert [m for m, _ in calls] == ["GET", "GET", "POST", "GET"]
    assert [p for m, p in calls if m == "POST"] == [
        f"/wayline/api/v1/workspaces/{WID}/waylines/file/upload"]


def test_failed_session_must_never_upload(monkeypatch):
    monkeypatch.setenv("AERONEXUS_PILOT_WAYLINE_UPLOAD_ENABLED", "1")
    calls = []
    with pytest.raises(UploadError, match="preflight_unavailable"):
        asyncio.run(upload(
            plan(), CREDS, expected_model="mavic3m", transport=httpx.MockTransport(
                handler_factory(calls, invalid_session=True))))
    assert [m for m, _ in calls] == ["GET"]


@pytest.mark.parametrize("post_code,after,network_failure,expected", [
    (9, True, False, "upload_rejected_or_outcome_unknown"),
    (0, False, False, None),
    (0, True, True, "upload_outcome_unknown"),
])
def test_dont_retry_or_assume_success(monkeypatch, post_code, after, network_failure, expected):
    monkeypatch.setenv("AERONEXUS_PILOT_WAYLINE_UPLOAD_ENABLED", "1")
    calls = []
    transport = httpx.MockTransport(handler_factory(
        calls, post_code=post_code, after=after, network_failure=network_failure))
    if expected:
        with pytest.raises(UploadError, match=expected):
            asyncio.run(upload(plan(), CREDS, expected_model="mavic3m", transport=transport))
    else:
        result = asyncio.run(upload(plan(), CREDS, expected_model="mavic3m", transport=transport))
        assert result["state"] == "submitted_unverified"
        assert result["verified"] is False
    assert sum(m == "POST" for m, _ in calls) == 1


def test_expected_m3m_profile_blocks_wrong_aircraft_without_any_http(monkeypatch):
    monkeypatch.setenv("AERONEXUS_PILOT_WAYLINE_UPLOAD_ENABLED", "1")
    calls = []
    with pytest.raises(UploadError, match="model_mismatch"):
        asyncio.run(upload(
            plan(), CREDS, expected_model="matrice4t",
            transport=httpx.MockTransport(handler_factory(calls))))
    assert calls == []


def test_model_confirmation_is_required_for_every_live_upload(monkeypatch):
    monkeypatch.setenv("AERONEXUS_PILOT_WAYLINE_UPLOAD_ENABLED", "1")
    calls = []
    with pytest.raises(UploadError, match="expected_model_required"):
        asyncio.run(upload(
            plan(), CREDS,
            transport=httpx.MockTransport(handler_factory(calls))))
    assert calls == []


def test_read_only_preflight_does_not_post_even_with_upload_flag_enabled(monkeypatch):
    from aeronexus.pilot_wayline_upload import check_cloud
    monkeypatch.setenv("AERONEXUS_PILOT_WAYLINE_UPLOAD_ENABLED", "1")
    calls = []
    result = asyncio.run(check_cloud(
        plan(), CREDS, transport=httpx.MockTransport(handler_factory(calls))))
    assert result["state"] == "connected"
    assert result["pagination_complete"]
    assert [method for method, _ in calls] == ["GET", "GET"]


def test_wrong_device_model_cannot_verify_new_cloud_wayline(monkeypatch):
    monkeypatch.setenv("AERONEXUS_PILOT_WAYLINE_UPLOAD_ENABLED", "1")
    calls = []
    delegate = handler_factory(calls)
    def wrong_model(request):
        response = delegate(request)
        if request.method == "GET" and request.url.path.endswith("/waylines"):
            payload = response.json()
            if payload["data"]["list"]:
                payload["data"]["list"][0]["drone_model_key"] = "0-99-1"
                return httpx.Response(200, json=payload)
        return response
    result = asyncio.run(upload(
        plan(), CREDS, expected_model="mavic3m",
        transport=httpx.MockTransport(wrong_model)))
    assert result["state"] == "submitted_unverified"
    assert result["verified"] is False
    assert sum(method == "POST" for method, _ in calls) == 1


def test_incomplete_post_upload_inventory_does_not_verify(monkeypatch):
    monkeypatch.setenv("AERONEXUS_PILOT_WAYLINE_UPLOAD_ENABLED", "1")
    calls = []
    delegate = handler_factory(calls)
    def partial_list(request):
        response = delegate(request)
        if request.method == "GET" and request.url.path.endswith("/waylines") and any(
                method == "POST" for method, _ in calls):
            payload = response.json()
            payload["data"]["pagination"]["total"] = 501
            payload["data"]["list"] = []
            # The adapter rejects this as inconsistent; it must never report success.
            return httpx.Response(200, json=payload)
        return response
    result = asyncio.run(upload(
        plan(), CREDS, expected_model="mavic3m",
        transport=httpx.MockTransport(partial_list)))
    assert result["verified"] is False
    assert sum(method == "POST" for method, _ in calls) == 1
