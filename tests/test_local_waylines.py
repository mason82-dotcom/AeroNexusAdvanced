"""Loopback-only scoped GETs; no remote flight/mutation or secret disclosure."""
import asyncio
import json
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from aeronexus import local_waylines as lw
from aeronexus.app import app
from aeronexus.mission_reconciliation import compare_missions
from aeronexus.status_runtime import StatusRuntime


WORKSPACE = "12345678-1234-4234-8234-123456789012"
CREDENTIALS = lw.Credentials(WORKSPACE, "local-session-secret-123456789")


def row(index=1, **extra):
    return {"id": str(UUID(int=index)), "name": "Dach Nord", "drone_model_key": "0-77-2",
            "template_types": [0], "update_time": 1792250000123,
            "object_key": "private/route.kmz", "user_name": "private-user",
            "sign": "private-sign", "url": "https://signed.invalid", **extra}


def envelope(items, page=1, size=50, total=None):
    return {"code": 0, "data": {"list": items,
            "pagination": {"page": page, "page_size": size, "total": len(items) if total is None else total}}}


def read(handler):
    return asyncio.run(lw.read_waylines(CREDENTIALS, transport=httpx.MockTransport(handler)))


def test_scoped_get_only_and_safe_data_units():
    def handler(request):
        assert request.method == "GET"
        assert str(request.url).startswith(lw.ORIGIN + "/wayline/api/v1/workspaces/" + WORKSPACE + "/waylines?")
        assert request.headers["x-auth-token"] == CREDENTIALS.access_token
        assert dict(request.url.params) == {"page": "1", "page_size": "50", "order_by": "create_time asc"}
        return httpx.Response(200, json=envelope([row()]))
    result = read(handler)
    item, = result["waylines"]
    assert item["device_model_key"] == "0-77-2"
    assert item["updated_at_ms"] == 1792250000123
    assert item["template_types"] == ["waypoint"]
    assert result["pagination_complete"] is True
    assert result["snapshot_consistency_verified"] is False
    assert "private" not in json.dumps(result)
    assert "signed.invalid" not in json.dumps(result)
    assert CREDENTIALS.access_token not in repr(CREDENTIALS)


def test_follows_all_pages_including_server_smaller_page_size():
    calls = []
    def handler(request):
        page = int(request.url.params["page"])
        calls.append(page)
        return httpx.Response(200, json=envelope([row(page)], page=page, size=1, total=3))
    result = read(handler)
    assert calls == [1, 2, 3]
    assert len(result["waylines"]) == 3
    assert result["pagination_complete"] is True


def test_limit_is_explicit_never_complete_claim():
    calls = []
    def handler(request):
        page = int(request.url.params["page"])
        calls.append(page)
        items = [row((page - 1) * 50 + i + 1) for i in range(50)]
        return httpx.Response(200, json=envelope(items, page=page, total=lw.MAX_PAGES * 50 + 1))
    result = read(handler)
    assert len(calls) == lw.MAX_PAGES and len(result["waylines"]) == lw.MAX_PAGES * 50
    assert result["reported_total"] == lw.MAX_PAGES * 50 + 1
    assert result["pagination_complete"] is False


def test_workspace_with_more_than_500_routes_reads_the_last_page():
    def handler(request):
        page = int(request.url.params["page"])
        start = (page - 1) * 50 + 1
        items = [row(i) for i in range(start, min(start + 50, 502))]
        return httpx.Response(200, json=envelope(items, page=page, total=501))
    result = read(handler)
    assert len(result["waylines"]) == 501
    assert result["pagination_complete"] is True
    assert result["waylines"][-1]["wayline_id"] == str(UUID(int=501))


def test_successfully_empty_is_connected():
    result = read(lambda _: httpx.Response(200, json=envelope([])))
    assert result["state"] == "connected" and result["waylines"] == []


@pytest.mark.parametrize("status,code", [(401, "authentication_required"), (403, "authentication_required"),
                                        (302, "upstream_error"), (500, "upstream_error")])
def test_no_redirects_or_response_text_in_errors(status, code):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, text="secret-raw-body", headers={"location": "https://external.invalid"})
    with pytest.raises(lw.LocalWaylineError, match="^" + code + "$"):
        read(handler)
    assert len(calls) == 1


@pytest.mark.parametrize("payload", [
    {"code": True, "data": {}}, {"code": 1, "message": "secret", "data": {}},
    {"code": 0, "data": []}, envelope([], page=0), envelope([], size=0),
    envelope([], total=True), envelope([], total=2), envelope([row(id="../invalid")]),
    envelope([row(template_types=[True])]), envelope([row(name="x" * 201)]),
])
def test_invalid_schema_cannot_masquerade_as_empty(payload):
    with pytest.raises(lw.LocalWaylineError):
        read(lambda _: httpx.Response(200, json=payload))


@pytest.mark.parametrize("kind", ["duplicate", "count_changed", "page_size_changed"])
def test_unstable_pagination_rejected(kind):
    def handler(request):
        page = int(request.url.params["page"])
        count = 3 if kind == "count_changed" and page == 2 else 2
        size = 2 if kind == "page_size_changed" and page == 2 else 1
        return httpx.Response(200, json=envelope([row(1 if kind == "duplicate" else page)], page=page, size=size, total=count))
    with pytest.raises(lw.LocalWaylineError, match="inventory_changed"):
        read(handler)


def test_oversized_response_rejected():
    with pytest.raises(lw.LocalWaylineError, match="invalid_response"):
        read(lambda _: httpx.Response(200, content=b" " * (lw.MAX_BODY + 1)))


def test_unknown_model_and_custom_template_codes_are_not_invented():
    result = read(lambda _: httpx.Response(200, json=envelope([row(drone_model_key="garbage", template_types=[4, 5])])) )
    item, = result["waylines"]
    assert item["device_model_key"] is None
    assert item["template_types"] == []
    assert item["template_type_codes"] == [4, 5]


def test_credentials_private_atomic_and_no_password(tmp_path):
    path = tmp_path / "private" / "session.json"
    lw.save_credentials(path, CREDENTIALS)
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    assert lw.load_credentials(path) == CREDENTIALS
    assert set(json.loads(path.read_text())) == {"workspace_id", "access_token"}
    path.chmod(0o644)
    with pytest.raises(lw.LocalWaylineError, match="configuration_error"):
        lw.load_credentials(path)


def test_missing_symlink_fifo_and_invalid_credentials(tmp_path):
    assert lw.load_credentials(tmp_path / "missing") is None
    real = tmp_path / "real"
    real.write_text("{}")
    real.chmod(0o600)
    link = tmp_path / "link"
    link.symlink_to(real)
    import os
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo, 0o600)
    for path in (real, link, fifo):
        with pytest.raises(lw.LocalWaylineError):
            lw.load_credentials(path)


@pytest.mark.parametrize("value", [{"workspace_id": "../../path", "access_token": "a" * 20},
                                   {"workspace_id": WORKSPACE, "access_token": "token\r\nsecret"}])
def test_credentials_reject_path_and_header_injection(value):
    with pytest.raises(lw.LocalWaylineError):
        lw.Credentials.parse(value)


def test_login_is_explicit_and_not_part_of_reader():
    def handler(request):
        assert request.method == "POST"
        assert str(request.url) == lw.ORIGIN + "/manage/api/v1/login"
        assert json.loads(request.content) == {"username": "account", "password": "password", "flag": 1}
        return httpx.Response(200, json={"code": 0, "data": {"workspace_id": WORKSPACE,
                                    "access_token": CREDENTIALS.access_token, "mqtt_password": "not-stored"}})
    result = asyncio.run(lw.login("account", "password", 1, transport=httpx.MockTransport(handler)))
    assert result == CREDENTIALS


def test_cache_coalescing_error_clears_data_rotation_and_removal(tmp_path, monkeypatch):
    path = tmp_path / "private" / "session.json"
    lw.save_credentials(path, CREDENTIALS)
    monkeypatch.setenv("AERONEXUS_LOCAL_WAYLINES_FILE", str(path))
    calls = []
    async def get(credentials):
        calls.append(credentials)
        if len(calls) == 2:
            raise lw.LocalWaylineError("authentication_required")
        return {"state": "connected", "waylines": [row()]}
    monkeypatch.setattr(lw, "read_waylines", get)
    async def run():
        reader = lw.LocalWaylineReader()
        await asyncio.gather(reader.read(), reader.read())
        assert len(calls) == 1
        reader._until = 0
        failed = await reader.read()
        assert failed == {"state": "authentication_required", "waylines": []}
        lw.save_credentials(path, lw.Credentials(WORKSPACE, "another-private-session-token"))
        assert (await reader.read())["state"] == "connected"
        assert len(calls) == 3
        path.unlink()
        assert (await reader.read())["state"] == "not_configured"
    asyncio.run(run())


def test_api_local_source_and_no_unauthorized_network(tmp_path, monkeypatch):
    token = "local-wayline-api-test-token-123456789"
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", token)
    monkeypatch.setenv("AERONEXUS_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.setattr(app.state, "status_runtime", StatusRuntime())
    calls = []
    async def fake_read(self, *, force=False):
        calls.append(force)
        result = await lw.read_waylines(CREDENTIALS, transport=httpx.MockTransport(lambda _: httpx.Response(200, json=envelope([row()]))))
        return result
    monkeypatch.setattr(lw.LocalWaylineReader, "read", fake_read)
    with TestClient(app) as client:
        url = "/api/v1/studio/missions/reconciliation"
        assert client.get(url).status_code == 401
        assert client.get(url + "?refresh=true").status_code == 401
        assert not calls
        headers = {"Authorization": "Bearer " + token}
        client.post("/api/v1/studio/missions", headers=headers, json={"name": "Dach Nord", "drone_model": "mavic3m"})
        response = client.get(url, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["coverage"]["pilot2_local_cloud"] == "connected"
        assert data["coverage"]["flighthub_cache_available"] is False
        candidate, = data["missions"][0]["candidates"]
        assert candidate["provider"] == "pilot2-local-cloud"
        assert candidate["workspace_id"] == WORKSPACE and candidate["model_match"] is True
        assert candidate["content_match"] is None
        assert data["local_pilot"]["pagination_complete"] is True
        assert "private" not in response.text and CREDENTIALS.access_token not in response.text
        assert response.headers["cache-control"] == "no-store"
        assert calls == [False]
        assert client.get(url + "?refresh=true", headers=headers).status_code == 200
        assert calls == [False, True]


@pytest.mark.parametrize("failure", ["network", "configuration"])
def test_reader_errors_are_sanitized_and_do_not_leak_secrets(tmp_path, monkeypatch, failure):
    path = tmp_path / "private" / "session.json"
    lw.save_credentials(path, CREDENTIALS)
    monkeypatch.setenv("AERONEXUS_LOCAL_WAYLINES_FILE", str(path))
    calls = []
    async def fake(credentials):
        calls.append(1)
        raise httpx.ConnectError("raw-private-error-with-token")
    monkeypatch.setattr(lw, "read_waylines", fake)
    if failure == "configuration":
        path.chmod(0o644)
    result = asyncio.run(lw.LocalWaylineReader().read())
    assert result["state"] == ("unavailable" if failure == "network" else "configuration_error")
    assert "private" not in json.dumps(result)
    assert len(calls) == (1 if failure == "network" else 0)


@pytest.mark.parametrize("verify_ok", [True, False])
def test_cli_configuration_verifies_before_replacing_session(tmp_path, monkeypatch, capsys, verify_ok):
    import sys
    path = tmp_path / "private" / "session.json"
    lw.save_credentials(path, CREDENTIALS)
    original = path.read_bytes()
    monkeypatch.setenv("AERONEXUS_LOCAL_WAYLINES_FILE", str(path))
    monkeypatch.setattr(sys, "argv", ["local_waylines", "--login"])
    monkeypatch.setattr("builtins.input", lambda _: "operator")
    monkeypatch.setattr(lw, "getpass", lambda _: "never-save-this-password")
    replacement = lw.Credentials(WORKSPACE, "replacement-private-session-token")
    async def login(username, password, flag):
        assert (username, password, flag) == ("operator", "never-save-this-password", 1)
        return replacement
    async def verify(credentials):
        assert credentials == replacement
        if not verify_ok:
            raise lw.LocalWaylineError("authentication_required")
        return {"state": "connected"}
    monkeypatch.setattr(lw, "login", login)
    monkeypatch.setattr(lw, "read_waylines", verify)
    assert lw.main() == (0 if verify_ok else 1)
    if verify_ok:
        assert lw.load_credentials(path) == replacement
    else:
        assert path.read_bytes() == original
    output = capsys.readouterr().out
    assert "never-save-this-password" not in output
    assert replacement.access_token not in output
    assert "never-save-this-password" not in path.read_text()


def test_explicit_refresh_reads_past_the_metadata_cache(tmp_path, monkeypatch):
    path = tmp_path / "private" / "session.json"
    lw.save_credentials(path, CREDENTIALS)
    monkeypatch.setenv("AERONEXUS_LOCAL_WAYLINES_FILE", str(path))
    calls = []

    async def get(credentials):
        calls.append(credentials)
        return {"state": "connected", "waylines": [row(i + 1) for i in range(len(calls))]}

    monkeypatch.setattr(lw, "read_waylines", get)

    async def run():
        reader = lw.LocalWaylineReader()
        assert len((await reader.read())["waylines"]) == 1
        assert len((await reader.read())["waylines"]) == 1
        assert len((await reader.read(force=True))["waylines"]) == 2
        assert len((await reader.read())["waylines"]) == 2
        assert len(calls) == 2

    asyncio.run(run())
