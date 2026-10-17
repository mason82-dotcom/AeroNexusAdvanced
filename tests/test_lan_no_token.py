"""Opt-in token-free HTTPS access from this Pi's private LAN only.

The legacy bearer-token mode remains in tests/test_status_api.py and
tests/test_studio_api.py. We explicitly simulate the real client IPv4 address.
"""
import asyncio
from io import BytesIO
from zipfile import ZipFile

import httpx
import pytest

from aeronexus.app import app
from aeronexus.inventory import Inventory, Device, DeviceType, Project
from aeronexus.providers import DeviceSnapshot, ProviderKind
from aeronexus.status_runtime import StatusRuntime


BASE = "https://192.168.178.63:8000"
LAN_ORIGIN = {"Origin": BASE, "Sec-Fetch-Site": "same-origin"}
M = {
    "name": "Testmission ohne Token",
    "drone_model": "matrice4t",
    "waypoints": [
        {"latitude": 49.12, "longitude": 8.5},
        {"latitude": 49.14, "longitude": 8.6, "take_photo": True},
    ],
}


@pytest.fixture
def lan(tmp_path, monkeypatch):
    monkeypatch.setenv("AERONEXUS_LAN_NO_TOKEN", "1")
    monkeypatch.setenv("AERONEXUS_LAN_HOST", "192.168.178.63")
    monkeypatch.delenv("AERONEXUS_STATUS_TOKEN", raising=False)
    monkeypatch.setenv("AERONEXUS_WORKSPACE_DIR", str(tmp_path / "workspace"))
    inventory = Inventory()
    provider = ProviderKind.PUBLIC_V2
    inventory.add_project(Project(provider, "p", "Testprojekt"))
    inventory.add_device(Device(provider, "p", "TESTAIRCRAFT", DeviceType.AIRCRAFT, "Matrice 4T"))
    inventory.update_telemetry("p", DeviceSnapshot(
        provider, "TESTAIRCRAFT", latitude=49.12, longitude=8.5, online=True,
        battery_percent=42))
    monkeypatch.setattr(app.state, "status_runtime", StatusRuntime(inventory))
    return tmp_path


def send(method, path, *, ip="192.168.178.44", base=BASE, headers=None, json=None, content=None):
    async def run():
        transport = httpx.ASGITransport(app=app, client=(ip, 45678))
        async with httpx.AsyncClient(transport=transport, base_url=base) as client:
            return await client.request(method, path, headers=headers, json=json, content=content)
    return asyncio.run(run())


def test_status_and_studio_open_without_any_token(lan):
    for endpoint in ("/status", "/studio"):
        page = send("GET", endpoint)
        assert page.status_code == 200
        assert page.headers["cache-control"] == "no-store"
        assert "auth-token" not in page.text
        assert 'id="token"' not in page.text
    status = send("GET", "/api/v1/status/devices")
    assert status.status_code == 200
    assert status.json()["devices"][0]["device_id"] == "TESTAIRCRAFT"
    assert status.json()["devices"][0]["telemetry"]["latitude"] == 49.12
    catalog = send("GET", "/api/v1/flighthub/catalog")
    assert catalog.status_code == 200
    assert catalog.json()["projects"] == []


def test_no_token_mission_create_update_export_delete(lan):
    made = send("POST", "/api/v1/studio/missions", headers=LAN_ORIGIN, json=M)
    assert made.status_code == 201, made.text
    item_id = made.json()["id"]
    assert send("GET", "/api/v1/studio/missions").json()["missions"][0]["id"] == item_id
    assert send("PUT", "/api/v1/studio/missions/" + item_id,
                headers=LAN_ORIGIN, json={**M, "name": "Geändert"}).status_code == 200
    exported = send("GET", "/api/v1/studio/missions/" + item_id + "/export.kmz")
    assert exported.status_code == 200
    with ZipFile(BytesIO(exported.content)) as archive:
        assert set(archive.namelist()) == {"wpmz/template.kml", "wpmz/waylines.wpml"}
    assert send("DELETE", "/api/v1/studio/missions/" + item_id,
                headers=LAN_ORIGIN).status_code == 204
    assert send("GET", "/api/v1/studio/missions/" + item_id).status_code == 404


def test_no_token_media_can_be_stored_and_read(lan):
    file = b"\x89PNG\r\n\x1a\n" + b"example-bytes"
    uploaded = send("POST", "/api/v1/studio/media", headers={
        **LAN_ORIGIN, "Content-Type": "image/png", "X-Filename": "test.png"}, content=file)
    assert uploaded.status_code == 201, uploaded.text
    item_id = uploaded.json()["id"]
    fetched = send("GET", f"/api/v1/studio/media/{item_id}/file")
    assert fetched.status_code == 200
    assert fetched.content == file
    assert send("DELETE", f"/api/v1/studio/media/{item_id}",
                headers=LAN_ORIGIN).status_code == 204


@pytest.mark.parametrize("ip", ["192.168.179.10", "8.8.8.8", "10.0.0.5", "172.16.0.8"])
def test_outside_lan_denied_even_when_token_free_enabled(lan, ip):
    assert send("GET", "/api/v1/status/devices", ip=ip).status_code == 403
    assert send("GET", "/api/v1/studio/missions", ip=ip).status_code == 403
    assert send("GET", "/status", ip=ip).status_code == 403


@pytest.mark.parametrize("url", [
    "https://attacker.example:8000",
    "https://192.168.178.64:8000",
    "http://192.168.178.63:8000",
])
def test_wrong_host_or_plaintext_denied(lan, url):
    assert send("GET", "/api/v1/status/devices", base=url).status_code == 403


def test_dns_rebinding_and_cross_site_protection(lan):
    for hdr in (
        {"Origin": "https://malicious.example", "Sec-Fetch-Site": "cross-site"},
        {"Origin": "https://192.168.178.63:9443", "Sec-Fetch-Site": "same-origin"},
        {"Sec-Fetch-Site": "cross-site"},
        {"X-Forwarded-For": "192.168.178.44"},
        {"Forwarded": "for=192.168.178.44"},
    ):
        assert send("GET", "/api/v1/studio/missions", headers=hdr).status_code == 403


def test_write_requires_matching_origin_or_same_origin_browser_metadata(lan):
    assert send("POST", "/api/v1/studio/missions", json=M).status_code == 403
    assert send("POST", "/api/v1/studio/missions",
                json=M, headers={"Sec-Fetch-Site": "same-origin"}).status_code == 201
    assert send("POST", "/api/v1/studio/missions", json=M, headers={
        "Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"}).status_code == 403


def test_missing_fixed_lan_host_configuration_denied(lan, monkeypatch):
    monkeypatch.delenv("AERONEXUS_LAN_HOST")
    assert send("GET", "/api/v1/status/devices").status_code == 503


def test_mode_is_explicit_opt_in(lan, monkeypatch):
    monkeypatch.delenv("AERONEXUS_LAN_NO_TOKEN")
    assert send("GET", "/api/v1/status/devices").status_code == 503


def test_dji_flight_commands_still_blocked(lan):
    assert send("POST", "/api/v1/flight/command",
                headers=LAN_ORIGIN).status_code == 403


@pytest.mark.parametrize("value,expected", [
    ("192.168.178.63", "192.168.178.63"), ("192.168.178.20", "192.168.178.20"),
    ("10.0.0.5", None), ("192.168.178.0", None), ("192.168.178.255", None),
    ("pi.local", None), ("", None), ("192.168.178.63:8000", None),
])
def test_lan_host_must_be_one_address_in_home_subnet(monkeypatch, value, expected):
    from aeronexus.lan_access import lan_host
    monkeypatch.setenv("AERONEXUS_LAN_HOST", value)
    assert lan_host() == expected


def test_studio_csp_socket_origin_follows_configuration(lan, monkeypatch):
    monkeypatch.setenv("AERONEXUS_LAN_HOST", "192.168.178.20")
    monkeypatch.setenv("AERONEXUS_PORT", "8443")
    r = send("GET", "/studio", base="https://192.168.178.20:8443")
    assert r.status_code == 200
    assert "wss://192.168.178.20:8443 " in r.headers["content-security-policy"]
    assert "192.168.178.63" not in r.headers["content-security-policy"]
