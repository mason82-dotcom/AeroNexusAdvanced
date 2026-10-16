"""DJI demo-shaped detailed status tests. No live DJI calls."""
import asyncio
from dataclasses import replace

import pytest

from aeronexus.flighthub_device_state import (
    DeviceStateError, normalize_aircraft_state, normalize_onprem_device,
    normalize_onprem_state_page, normalize_public_state,
    read_onprem_aircraft_states, read_public_aircraft_state,
    sync_public_aircraft_state,
)
from aeronexus.inventory import Device, DeviceType, Inventory, Project
from aeronexus.providers import ProviderConfig, ProviderKind
from aeronexus.read_only_transport import ReadOnlyTransport
from aeronexus.telemetry_sync import TelemetrySyncError, parse_snapshot, register_snapshots

PUBLIC = ProviderKind.PUBLIC_V2
ONPREM = ProviderKind.ONPREM_V2
PROJECT = "93df839d-ae74-4f04-842e-2f1f81c89a66"
ORG = "105ddd05-34ce-46b6-a872-cb32b8c98f64"
SN = "1ZRDH3V000000TEST"
PC = ProviderConfig(PUBLIC, "https://api-openapi.dji.com", "fake-token")
OC = ProviderConfig(ONPREM, "https://local.example", "fake-token")


def state():
    return {
        "latitude": 49.251, "longitude": 8.505,
        "height": 52.5, "horizontal_speed": 8.1, "vertical_speed": -0.5,
        "total_flight_time": 3600, "total_flight_sorties": 12,
        "battery": {"capacity_percent": 83, "voltage": 23700, "temperature": 25.5},
        "position_state": {
            "rtk_number": 17, "gps_number": 23, "is_fixed": "not_started",
        },
        "device_online_status": "power_on",
    }


def response():
    return {"code": 0, "data": {"device_state": state()}}


def make_inventory(kind=DeviceType.AIRCRAFT):
    inv = Inventory()
    inv.add_project(Project(PUBLIC, PROJECT, "Survey"))
    inv.add_device(Device(PUBLIC, PROJECT, SN, kind, "Aircraft"))
    return inv


def test_normalize_public_flight_metrics():
    snap = normalize_public_state(SN, response())
    assert (snap.latitude, snap.longitude) == (49.251, 8.505)
    assert snap.online is True and snap.battery_percent == 83
    assert snap.height_m == 52.5
    assert snap.horizontal_speed_mps == 8.1
    assert snap.vertical_speed_mps == -0.5
    assert snap.total_flight_time_s == 3600
    assert snap.total_flight_sorties == 12
    assert (snap.gps_satellites, snap.rtk_satellites) == (23, 17)
    assert snap.rtk_state == "is_fixed:not_started"
    assert snap.battery_voltage_mv == 23700
    assert snap.battery_temperature_c == 25.5


def test_direct_state_wrapper():
    result = normalize_public_state(SN, {"code": 0, "data": state()})
    assert result.battery_percent == 83


def test_parent_online_when_state_omits_status():
    result = normalize_public_state(SN, {"code": 0, "data": {
        "device_online_status": "power_off", "device_state": {"height": 1}}})
    assert result.online is False


@pytest.mark.parametrize("raw,expected", [
    ("power_on", True), ("online", True), ("power_off", False),
    ("offline", False), (0, False), (1, True), (True, True),
    (False, False), (None, None),
])
def test_online_mapping(raw, expected):
    assert normalize_aircraft_state(PUBLIC, SN, {"device_online_status": raw}).online is expected


@pytest.mark.parametrize("field,value", [
    ("latitude", 91), ("horizontal_speed", -1),
    ("vertical_speed", float("nan")), ("height", float("inf")),
    ("total_flight_sorties", 1.5), ("total_flight_time", -1),
    ("device_online_status", "maybe"), ("device_online_status", 3),
])
def test_reject_invalid_public_metrics(field, value):
    data = state()
    data[field] = value
    with pytest.raises(ValueError):
        normalize_public_state(SN, {"code": 0, "data": {"device_state": data}})


@pytest.mark.parametrize("position", [
    {"rtk_number": -1}, {"rtk_number": 5.0}, {"gps_number": True},
    {"is_fixed": True}, {"is_fixed": ""},
])
def test_reject_invalid_position(position):
    with pytest.raises(ValueError):
        normalize_public_state(SN, {"code": 0, "data": {
            "device_state": {"position_state": position}}})


def test_rtk_satellite_count_does_not_imply_fix():
    result = normalize_aircraft_state(PUBLIC, SN, {
        "position_state": {"rtk_number": 20}})
    assert result.rtk_satellites == 20
    assert result.rtk_state is None


def test_rtk_numeric_code_preserved_not_interpreted():
    result = normalize_aircraft_state(ONPREM, SN, {
        "position_state": {"is_fixed": 1}})
    assert result.rtk_state == "is_fixed:1"


def test_partial_coordinate_is_rejected():
    with pytest.raises(TelemetrySyncError):
        normalize_aircraft_state(PUBLIC, SN, {"latitude": 49.0})


@pytest.mark.parametrize("invalid", [
    "../x", "sn/other", "sn?x=1", "sn%2Fother", "with space",
    "", "A" * 81,
])
def test_reject_unsafe_serials(invalid):
    with pytest.raises(DeviceStateError):
        asyncio.run(read_public_aircraft_state(PC, PROJECT, invalid))


@pytest.mark.parametrize("payload", [
    {"code": 1, "data": {}},
    {"code": True, "data": {}},
    {"code": 0}, {"code": 0, "data": []},
    {"code": 0, "data": {"device_state": None}},
    {"code": 0, "data": {"sn": "different", "device_state": {}}},
    {"code": 0, "data": {"device_state": {"device_sn": "different"}}},
])
def test_reject_invalid_dji_payload(payload):
    with pytest.raises(DeviceStateError):
        normalize_public_state(SN, payload)


def test_onprem_inline_device_state():
    record = {"device_sn": SN, "device_model": {"class": "drone"},
              "device_online_status": False, "device_state": state()}
    record["device_state"].pop("device_online_status")
    snapshot = normalize_onprem_device(record)
    assert snapshot.online is False
    assert snapshot.battery_percent == 83
    assert snapshot.total_flight_sorties == 12


def test_onprem_list_filters_infrastructure():
    record = {"device_sn": SN, "device_model": {"class": "drone"},
              "device_online_status": True, "device_state": {"height": 12}}
    payload = {"code": 0, "data": {"list": [
        {"device_sn": "NOT-AN-AIRCRAFT", "device_model": {"class": "airport"}},
        {"device_sn": "RELAY", "device_model": {"class": "relay"}},
        record,
    ]}}
    results = normalize_onprem_state_page(payload)
    assert len(results) == 1 and results[0].device_id == SN


def test_onprem_rejects_infrastructure_directly():
    with pytest.raises(DeviceStateError, match="Not an aircraft"):
        normalize_onprem_device({"device_sn": "dock-1",
                                "device_model": {"class": "dock"}})


def test_onprem_rejects_duplicate():
    row = {"device_sn": SN, "device_model": {"class": "drone"}}
    with pytest.raises(DeviceStateError, match="Duplicate"):
        normalize_onprem_state_page({"code": 0, "data": {"list": [row, row]}})


def test_public_get_uses_project_scoped_allowlist(monkeypatch):
    seen = {}
    async def fake_get(self, path, params=None, *, project_uuid=None):
        seen.update(path=path, params=params, project_uuid=project_uuid)
        return response()
    monkeypatch.setattr(ReadOnlyTransport, "get", fake_get)
    snapshot = asyncio.run(read_public_aircraft_state(PC, PROJECT, SN))
    assert snapshot.height_m == 52.5
    assert seen == {
        "path": f"/openapi/v2.0/device/{SN}/state",
        "params": None, "project_uuid": PROJECT,
    }


def test_onprem_get_uses_readonly_paginated_list(monkeypatch):
    seen = {}
    async def fake_get(self, path, params=None, *, project_uuid=None):
        seen.update(path=path, params=params, project_uuid=project_uuid)
        return {"code": 0, "data": {"list": [
            {"device_sn": SN, "device_model": {"class": "drone"},
             "device_online_status": False, "device_state": {"height": 7}}]}}
    monkeypatch.setattr(ReadOnlyTransport, "get", fake_get)
    snapshots = asyncio.run(read_onprem_aircraft_states(OC, ORG, page=2, page_size=10))
    assert len(snapshots) == 1 and snapshots[0].height_m == 7
    assert seen["path"].endswith(f"/organizations/{ORG}/manage-devices")
    assert seen["params"] == {"device_model_class": "drone", "page": 2, "page_size": 10}
    assert seen["project_uuid"] is None


@pytest.mark.parametrize("page,size", [
    (0, 20), (1, 0), (1, 101), (True, 20), (1, False),
])
def test_onprem_rejects_pagination(page, size):
    with pytest.raises(DeviceStateError):
        asyncio.run(read_onprem_aircraft_states(OC, ORG, page=page, page_size=size))


def test_reject_wrong_provider_and_uuid():
    with pytest.raises(DeviceStateError):
        asyncio.run(read_public_aircraft_state(OC, PROJECT, SN))
    with pytest.raises(DeviceStateError):
        asyncio.run(read_onprem_aircraft_states(PC, ORG))
    with pytest.raises(DeviceStateError):
        asyncio.run(read_public_aircraft_state(PC, "../bad", SN))
    with pytest.raises(DeviceStateError):
        asyncio.run(read_onprem_aircraft_states(OC, "../bad"))


def test_sync_detail_updates_registered_aircraft(monkeypatch):
    async def fake_get(self, path, params=None, *, project_uuid=None):
        return response()
    monkeypatch.setattr(ReadOnlyTransport, "get", fake_get)
    inv = make_inventory()
    detail = asyncio.run(sync_public_aircraft_state(inv, PC, PROJECT, SN))
    assert detail.height_m == 52.5
    assert inv.telemetry(PUBLIC, PROJECT, SN) == detail


def test_sync_keeps_previous_online_if_detail_omits(monkeypatch):
    async def fake_get(self, path, params=None, *, project_uuid=None):
        return {"code": 0, "data": {"device_state": {"height": 5}}}
    monkeypatch.setattr(ReadOnlyTransport, "get", fake_get)
    inv = make_inventory()
    initial = parse_snapshot(PUBLIC, {"device_id": SN, "online": True})
    register_snapshots(inv, PROJECT, (initial,))
    result = asyncio.run(sync_public_aircraft_state(inv, PC, PROJECT, SN))
    assert result.height_m == 5
    assert result.online is True


def test_sync_rejects_unregistered_before_network(monkeypatch):
    async def forbidden_get(*args, **kwargs):
        raise AssertionError("Network not allowed")
    monkeypatch.setattr(ReadOnlyTransport, "get", forbidden_get)
    inv = Inventory()
    with pytest.raises(DeviceStateError, match="Registered"):
        asyncio.run(sync_public_aircraft_state(inv, PC, PROJECT, SN))


def test_sync_rejects_controller_before_network(monkeypatch):
    async def forbidden_get(*args, **kwargs):
        raise AssertionError("Network not allowed")
    monkeypatch.setattr(ReadOnlyTransport, "get", forbidden_get)
    inv = make_inventory(DeviceType.CONTROLLER)
    with pytest.raises(DeviceStateError, match="Registered"):
        asyncio.run(sync_public_aircraft_state(inv, PC, PROJECT, SN))


def test_sync_bad_detail_does_not_change_inventory(monkeypatch):
    async def fake_get(self, path, params=None, *, project_uuid=None):
        return {"code": 0, "data": {"device_state": {
            "battery": {"capacity_percent": 108}}}}
    monkeypatch.setattr(ReadOnlyTransport, "get", fake_get)
    inv = make_inventory()
    original = parse_snapshot(PUBLIC, {"device_id": SN, "online": False})
    register_snapshots(inv, PROJECT, (original,))
    with pytest.raises(ValueError):
        asyncio.run(sync_public_aircraft_state(inv, PC, PROJECT, SN))
    assert inv.telemetry(PUBLIC, PROJECT, SN) == original


@pytest.mark.parametrize("field,value", [
    ("rtk_satellites", -1), ("gps_satellites", 5.5),
    ("total_flight_sorties", True), ("battery_voltage_mv", -3),
    ("battery_temperature_c", float("inf")),
])
def test_manually_constructed_invalid_extended_snapshot(field, value):
    inv = make_inventory()
    initial = parse_snapshot(PUBLIC, {"device_id": SN})
    corrupted = replace(initial, **{field: value})
    with pytest.raises(TelemetrySyncError):
        register_snapshots(inv, PROJECT, (corrupted,))
    assert inv.telemetry(PUBLIC, PROJECT, SN) is None
