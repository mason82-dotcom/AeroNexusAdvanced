"""DJI official demo-shaped read-only device-list fixtures, no network access."""
import asyncio

import pytest

from aeronexus.flighthub_device_list import (
    PUBLIC_LIST, DeviceListError, normalize_public_topology,
    normalize_onprem_page, read_public_aircraft, read_onprem_aircraft,
    sync_public_aircraft,
)
from aeronexus.inventory import Inventory, Project
from aeronexus.providers import ProviderConfig, ProviderKind
from aeronexus.read_only_transport import ReadOnlyTransport

PUBLIC = ProviderKind.PUBLIC_V2
ONPREM = ProviderKind.ONPREM_V2
PROJECT = "93df839d-ae74-4f04-842e-2f1f81c89a66"
ORG = "105ddd05-34ce-46b6-a872-cb32b8c98f64"
PC = ProviderConfig(PUBLIC, "https://api-openapi.dji.com", "not-a-real-token")
OC = ProviderConfig(ONPREM, "https://local.example", "not-a-real-token")


def public_payload():
    return {"code": 0, "data": {"list": [
        {"gateway": {"sn": "INFRASTRUCTURE1", "callsign": "Not imported",
                     "device_model": {"class": "airport"}},
         "drone": {"sn": "AIRCRAFT1", "callsign": "Matrice",
                   "device_model": {"class": "drone", "name": "M350"},
                   "device_online_status": 1,
                   "device_state": {"battery": {"capacity_percent": 80}}}},
        {"gateway": {"sn": "INFRASTRUCTURE2", "device_model": {"class": "airport"}},
         "drone": None},
    ]}}


def onprem_payload():
    return {"code": 0, "data": {"pagination": {"total": 2}, "list": [
        {"device_sn": "AIRCRAFT2", "device_callsign": "Mavic",
         "device_model": {"class": "drone", "name": "Mavic 3E"},
         "device_online_status": False, "device_active_project_name": "Survey",
         "device_state": {"drone_battery_maintenance_info": {
             "batteries": [{"capacity_percent": 67}]}}},
        {"device_sn": "INFRASTRUCTURE", "device_model": {"class": "base_station"}},
    ]}}


def test_public_topology_ignores_gateway():
    result = normalize_public_topology(public_payload())
    assert len(result) == 1
    assert result[0].device_id == "AIRCRAFT1"
    assert result[0].online is True
    assert result[0].battery_percent == 80


def test_onprem_page_ignores_non_aircraft():
    result = normalize_onprem_page(onprem_payload())
    assert len(result) == 1
    assert result[0].device_id == "AIRCRAFT2"
    assert result[0].project_name == "Survey"
    assert result[0].online is False
    assert result[0].battery_percent == 67


def test_public_ignores_unexpected_drone_class():
    payload = {"data": {"list": [{"drone": {
        "sn": "NOTDRONE", "device_model": {"class": "base_station"}}}]}}
    assert normalize_public_topology(payload) == ()


@pytest.mark.parametrize("payload", [
    {}, {"data": {}}, {"data": {"list": "invalid"}},
    {"data": {"list": [42]}}, {"data": {"list": [{"drone": "invalid"}]}},
    {"data": {"list": [{"drone": {"device_online_status": True}}]}},
    {"data": {"list": [{"drone": {"sn": "x", "device_online_status": "unknown"}}]}},
    {"data": {"list": [{"drone": {"sn": "x", "device_online_status": 2}}]}},
    {"data": {"list": [{"drone": {"sn": "x", "device_state": {"battery": {"capacity_percent": 120}}}}]}},
])
def test_reject_bad_public(payload):
    with pytest.raises(ValueError):
        normalize_public_topology(payload)


def test_reject_duplicate_public():
    row = {"drone": {"sn": "x"}}
    with pytest.raises(DeviceListError, match="Duplicate"):
        normalize_public_topology({"data": {"list": [row, row]}})


def test_onprem_ignores_other_classes():
    assert normalize_onprem_page({"data": {"list": [
        {"device_model": {"class": "airport"}},
        {"device_model": {"class": "base_station"}},
        {"device_model": {"class": "relay"}},
        {"device_model": {"class": "remote_controller"}},
    ]}}) == ()


def test_onprem_rejects_bad_battery():
    with pytest.raises(ValueError):
        normalize_onprem_page({"data": {"list": [{
            "device_sn": "x", "device_model": {"class": "drone"},
            "device_state": {"battery": {"capacity_percent": -1}}
        }]}})


def test_public_read_uses_project_header(monkeypatch):
    observed = {}
    async def fake_get(self, path, params=None, *, project_uuid=None):
        observed.update(path=path, params=params, project_uuid=project_uuid)
        return public_payload()
    monkeypatch.setattr(ReadOnlyTransport, "get", fake_get)
    aircraft = asyncio.run(read_public_aircraft(PC, PROJECT))
    assert len(aircraft) == 1
    assert observed == {"path": PUBLIC_LIST, "params": None, "project_uuid": PROJECT}


def test_onprem_read_uses_documented_page(monkeypatch):
    observed = {}
    async def fake_get(self, path, params=None, *, project_uuid=None):
        observed.update(path=path, params=params, project_uuid=project_uuid)
        return onprem_payload()
    monkeypatch.setattr(ReadOnlyTransport, "get", fake_get)
    aircraft = asyncio.run(read_onprem_aircraft(OC, ORG, page=2, page_size=50))
    assert len(aircraft) == 1
    assert observed["path"].endswith(f"/organizations/{ORG}/manage-devices")
    assert observed["params"] == {"device_model_class": "drone", "page": 2, "page_size": 50}
    assert observed["project_uuid"] is None


@pytest.mark.parametrize("page,size", [(0,20),(1,0),(1,101),(True,20),(1,False)])
def test_onprem_rejects_bad_page(page, size):
    with pytest.raises(DeviceListError):
        asyncio.run(read_onprem_aircraft(OC, ORG, page=page, page_size=size))


def test_wrong_provider_rejected():
    with pytest.raises(DeviceListError):
        asyncio.run(read_onprem_aircraft(PC, ORG))
    with pytest.raises(DeviceListError):
        asyncio.run(read_public_aircraft(OC, PROJECT))


def test_invalid_uuids_rejected():
    with pytest.raises(DeviceListError):
        asyncio.run(read_onprem_aircraft(OC, "../bad"))
    with pytest.raises(DeviceListError):
        asyncio.run(read_public_aircraft(PC, "../bad"))


def test_sync_public_imports_only_aircraft(monkeypatch):
    async def fake_get(self, path, params=None, *, project_uuid=None):
        return public_payload()
    monkeypatch.setattr(ReadOnlyTransport, "get", fake_get)
    inv = Inventory()
    inv.add_project(Project(PUBLIC, PROJECT, "Survey"))
    assert asyncio.run(sync_public_aircraft(inv, PC, PROJECT)) == (1, 1)
    assert {d.device_id for d in inv.devices()} == {"AIRCRAFT1"}
    assert inv.telemetry(PUBLIC, PROJECT, "AIRCRAFT1").battery_percent == 80


def test_sync_public_requires_registered_project():
    with pytest.raises(DeviceListError, match="registered"):
        asyncio.run(sync_public_aircraft(Inventory(), PC, PROJECT))


def test_sync_public_is_atomic_on_bad_state(monkeypatch):
    async def fake_get(self, path, params=None, *, project_uuid=None):
        payload = public_payload()
        payload["data"]["list"][0]["drone"]["device_state"]["battery"]["capacity_percent"] = 999
        return payload
    monkeypatch.setattr(ReadOnlyTransport, "get", fake_get)
    inv = Inventory()
    inv.add_project(Project(PUBLIC, PROJECT, "Survey"))
    with pytest.raises(ValueError):
        asyncio.run(sync_public_aircraft(inv, PC, PROJECT))
    assert inv.devices() == ()
