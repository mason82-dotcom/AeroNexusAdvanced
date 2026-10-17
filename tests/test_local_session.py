"""An existing server-authenticated session replaces another password prompt."""
import asyncio
import importlib.util
import json
from pathlib import Path
import sys

import httpx
import pytest
from fastapi.testclient import TestClient

from aeronexus.app import app
from aeronexus import local_session as session
from aeronexus import local_waylines as lw


WS = "12345678-1234-4234-8234-123456789012"
CREDS = lw.Credentials(WS, "browser-existing-session-123456789")
ORIGIN = "http://192.168.178.63:8085"
PATH = "/api/v1/local-cloud/session"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    file = tmp_path / "private" / "session.json"
    monkeypatch.setenv("AERONEXUS_LOCAL_WAYLINES_FILE", str(file))
    monkeypatch.setenv("AERONEXUS_LAN_NO_TOKEN", "1")
    monkeypatch.setenv("AERONEXUS_LAN_HOST", "192.168.178.63")
    lw.save_private_json(lw.handoff_path(), {"enabled": True})
    return file


def test_configure_no_longer_asks_for_credentials(tmp_path, monkeypatch, capsys):
    file = tmp_path / "private" / "session.json"
    monkeypatch.setenv("AERONEXUS_LOCAL_WAYLINES_FILE", str(file))
    monkeypatch.setattr(sys, "argv", ["local_waylines", "--configure"])
    def forbidden(*args):
        raise AssertionError("No password or username prompt permitted")
    monkeypatch.setattr("builtins.input", forbidden)
    monkeypatch.setattr(lw, "getpass", forbidden)
    monkeypatch.setattr(lw, "login", forbidden)
    assert lw.main() == 0
    assert lw.handoff_enabled()
    assert not file.exists()
    assert "Warte auf" in capsys.readouterr().out


def test_verified_current_user_not_unsigned_jwt_decode():
    def handler(request):
        assert request.method == "GET"
        assert str(request.url) == lw.ORIGIN + "/manage/api/v1/users/current"
        assert request.headers["x-auth-token"] == CREDS.access_token
        return httpx.Response(200, json={"code": 0, "data": {
            "workspace_id": WS, "user_type": 2, "mqtt_password": "discard"}})
    asyncio.run(session.verify_session(CREDS, transport=httpx.MockTransport(handler)))


@pytest.mark.parametrize("user", [{"workspace_id": "other", "user_type": 1},
                                  {"workspace_id": WS, "user_type": True},
                                  {"workspace_id": WS, "user_type": 3}])
def test_handoff_rejects_forged_scope_or_user_type(user):
    with pytest.raises(lw.LocalWaylineError):
        asyncio.run(session.verify_session(CREDS, transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"code": 0, "data": user}))))


def test_handoff_verifies_once_rotates_and_pins_workspace(setup, monkeypatch):
    calls = []
    async def verify(credentials):
        calls.append(credentials)
    monkeypatch.setattr(session, "verify_session", verify)
    async def run():
        handoff = session.LocalSessionHandoff()
        await handoff.accept(CREDS)
        await handoff.accept(CREDS)
        assert calls == [CREDS]
        rotated = lw.Credentials(WS, "new-browser-session-123456789")
        await handoff.accept(rotated)
        assert lw.load_credentials(setup) == rotated
        other = lw.Credentials("22345678-1234-4234-8234-123456789012", CREDS.access_token)
        with pytest.raises(lw.LocalWaylineError, match="workspace_conflict"):
            await handoff.accept(other)
        assert lw.load_credentials(setup) == rotated
    asyncio.run(run())


@pytest.mark.parametrize("origin", [None, "null", "https://evil.invalid", "http://192.168.178.63:8000", "http://192.168.178.63:8085/", "https://192.168.178.63:8085"])
def test_cors_rejects_all_other_origins_before_verification(setup, monkeypatch, origin):
    async def forbidden(*args):
        raise AssertionError("No network before origin authorization")
    monkeypatch.setattr(session, "verify_session", forbidden)
    with TestClient(app, base_url="https://192.168.178.63:8000", client=("192.168.178.20", 1234)) as client:
        headers = {"Origin": origin} if origin is not None else {}
        response = client.post(PATH, json={"workspace_id": WS, "access_token": CREDS.access_token}, headers=headers)
        assert response.status_code == 403
        assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("url,peer,enabled", [("http://192.168.178.63:8000", "192.168.178.20", True),
                                             ("https://192.168.178.63:8000", "203.0.113.1", True),
                                             ("https://192.168.178.63:8000", "192.168.178.20", False)])
def test_handoff_requires_direct_https_lan_and_explicit_opt_in(setup, url, peer, enabled):
    if not enabled:
        lw.handoff_path().unlink()
    with TestClient(app, base_url=url, client=(peer, 1234)) as client:
        assert client.post(PATH, json={}, headers={"Origin": ORIGIN}).status_code == 403


def test_preflight_post_and_private_storage_without_token_disclosure(setup, monkeypatch):
    async def verify(credentials):
        assert credentials == CREDS
    monkeypatch.setattr(session, "verify_session", verify)
    with TestClient(app, base_url="https://192.168.178.63:8000", client=("192.168.178.20", 1234)) as client:
        response = client.options(PATH, headers={"Origin": ORIGIN, "Access-Control-Request-Method": "POST",
                                                "Access-Control-Request-Headers": "content-type"})
        assert response.status_code == 204
        assert response.headers["access-control-allow-origin"] == ORIGIN
        response = client.post(PATH, json={"workspace_id": WS, "access_token": CREDS.access_token}, headers={"Origin": ORIGIN})
        assert response.status_code == 204
        assert response.headers["cache-control"] == "no-store"
        assert CREDS.access_token not in response.text
        assert lw.load_credentials(setup) == CREDS
        assert setup.stat().st_mode & 0o777 == 0o600


def test_failed_server_auth_keeps_previous_session(setup, monkeypatch):
    lw.save_credentials(setup, CREDS)
    async def reject(credentials):
        raise lw.LocalWaylineError("authentication_required")
    monkeypatch.setattr(session, "verify_session", reject)
    with TestClient(app, base_url="https://192.168.178.63:8000", client=("192.168.178.20", 1234)) as client:
        response = client.post(PATH, json={"workspace_id": WS, "access_token": "forged-session-token"}, headers={"Origin": ORIGIN})
        assert response.status_code == 403
        assert lw.load_credentials(setup) == CREDS


def test_web_installer_idempotent_and_dry_run(tmp_path):
    path = Path(__file__).resolve().parents[1] / "scripts/enable_wayline_session_handoff.py"
    spec = importlib.util.spec_from_file_location("handoff_installer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    web = tmp_path / "web"
    (web / "src/types").mkdir(parents=True)
    (web / "src/types/enums.ts").write_text("'x-auth-token' 'workspace_id' 'flag'")
    index = web / "index.html"
    index.write_text("<html><body>existing app</body></html>")
    original = index.read_text()
    asset = path.parents[1] / "deploy/cloud-server/aeronexus-wayline-session.js"
    assert module.install(web, asset)
    assert index.read_text() == original
    assert module.install(web, asset, apply=True)
    assert index.read_text().count(module.TAG) == 1
    assert not module.install(web, asset, apply=True)
    assert (web / ".aeronexus-session-index.backup").read_text() == original
