"""Dashboard access controls and read-only telemetry presentation."""
import json

import pytest
from fastapi.testclient import TestClient

from aeronexus.app import app
from aeronexus.inventory import Device, DeviceType, Inventory, Project
from aeronexus.providers import DeviceSnapshot, ProviderKind
from aeronexus.status_runtime import StatusRuntime, StatusSettings
from aeronexus.status_page import render_page


TOKEN = "aeronexus-status-token-not-dji-secret-123456"
PUBLIC = ProviderKind.PUBLIC_V2
ONPREM = ProviderKind.ONPREM_V2


@pytest.fixture
def api(monkeypatch):
    inventory = Inventory()
    inventory.add_project(Project(PUBLIC, "project", "Public project"))
    inventory.add_device(Device(PUBLIC, "project", "ABC123", DeviceType.AIRCRAFT, "Matrice"))
    inventory.add_device(Device(PUBLIC, "project", "RC456", DeviceType.CONTROLLER, "RC"))
    inventory.update_telemetry("project", DeviceSnapshot(
        PUBLIC, "ABC123", online=True, latitude=49.245,
        longitude=8.512, battery_percent=55))
    inventory.add_project(Project(ONPREM, "project", "Private project"))
    inventory.add_device(Device(ONPREM, "project", "DEF789", DeviceType.AIRCRAFT, "Other"))
    monkeypatch.setattr(app.state, "status_runtime", StatusRuntime(
        inventory, StatusSettings(90, 30)))
    monkeypatch.delenv("AERONEXUS_STATUS_TOKEN", raising=False)
    with TestClient(app) as client:
        yield client


def test_anonymous_summary_without_identifiers(api):
    res = api.get("/api/v1/status/summary")
    assert res.status_code == 200
    d = res.json()
    assert d["registered_devices"] == 3
    assert d["aircraft"] == 2 and d["controllers"] == 1
    assert d["online_fresh"] == 1
    assert d["missing"] == 2
    assert d["polling"] == "disabled"
    assert "ABC123" not in res.text
    assert "49.245" not in res.text
    assert res.headers["cache-control"] == "no-store"


def test_detail_requires_configured_token(api):
    res = api.get("/api/v1/status/devices")
    assert res.status_code == 503
    assert "ABC123" not in res.text


def test_weak_configured_token_denied(api, monkeypatch):
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", "weak")
    res = api.get("/api/v1/status/devices", headers={"Authorization": "Bearer weak"})
    assert res.status_code == 503
    assert "ABC123" not in res.text


@pytest.mark.parametrize("authorization", [
    None, "Bearer wrong", "Basic abc", "Bearer ",
    "Bearer " + ("A" * 520),
])
def test_detail_denies_invalid_credentials(api, monkeypatch, authorization):
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    headers = {"Authorization": authorization} if authorization is not None else {}
    res = api.get("/api/v1/status/devices", headers=headers)
    assert res.status_code == 401
    assert res.headers["www-authenticate"] == "Bearer"
    assert "ABC123" not in res.text
    assert "49.245" not in res.text


def test_authenticated_details(api, monkeypatch):
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    res = api.get("/api/v1/status/devices",
                  headers={"Authorization": "Bearer " + TOKEN})
    assert res.status_code == 200
    d = res.json()
    assert d["total"] == 3
    assert len(d["devices"]) == 3
    aircraft = next(x for x in d["devices"] if x["device_id"] == "ABC123")
    assert aircraft["online"] is True
    assert aircraft["freshness"] == "fresh"
    assert aircraft["telemetry"]["battery_percent"] == 55
    assert aircraft["telemetry"]["latitude"] == 49.245
    assert aircraft["received_at"].endswith("Z")
    assert res.headers["cache-control"] == "no-store"
    assert res.headers["x-content-type-options"] == "nosniff"


def test_filter_provider_and_project(api, monkeypatch):
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    headers = {"Authorization": "Bearer " + TOKEN}
    res = api.get("/api/v1/status/devices?provider=flighthub-onprem-v2&project_id=project",
                  headers=headers)
    assert res.status_code == 200
    assert [x["device_id"] for x in res.json()["devices"]] == ["DEF789"]


def test_pagination(api, monkeypatch):
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    headers = {"Authorization": "Bearer " + TOKEN}
    res = api.get("/api/v1/status/devices?limit=1&offset=1", headers=headers)
    assert res.status_code == 200
    assert res.json()["total"] == 3
    assert len(res.json()["devices"]) == 1
    assert res.json()["offset"] == 1


@pytest.mark.parametrize("suffix", ["?limit=0", "?limit=201", "?offset=-1", "?provider=invalid"])
def test_invalid_filters(api, monkeypatch, suffix):
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    res = api.get("/api/v1/status/devices" + suffix,
                  headers={"Authorization": "Bearer " + TOKEN})
    assert res.status_code == 422


def test_page_auto_refresh_and_not_expose_identifiers(api):
    res = api.get("/status")
    assert res.status_code == 200
    assert "setInterval" in res.text and "30000" in res.text
    assert "AeroNexusAdvanced" in res.text
    assert "ABC123" not in res.text
    assert res.headers["cache-control"] == "no-store"
    assert res.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in res.headers["content-security-policy"]


def test_page_refresh_validation():
    assert "12000" in render_page(12)
    for value in (0, 3601, True):
        with pytest.raises(ValueError):
            render_page(value)


def test_flight_commands_still_forbidden(api):
    assert api.post("/api/v1/flight/command").status_code == 403
