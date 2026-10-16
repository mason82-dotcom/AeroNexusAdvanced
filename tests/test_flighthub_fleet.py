"""Spec-shaped FlightHub V2 fleet fixtures (aircraft + RC), no network access."""
import asyncio
import time

import pytest

from aeronexus.flighthub_fleet import (
    FleetError, PUBLIC_PROJECT_DEVICES, commit_fleet, normalize_onprem_topologies,
    normalize_public_project_devices, read_onprem_fleet, read_public_fleet,
    snapshot, sync_project_fleet,
)
from aeronexus.flighthub_poller import FlightHubFleetRefresher, FlightHubPollSettings
from aeronexus.inventory import DeviceType, Inventory, Project
from aeronexus.providers import ProviderConfig, ProviderKind
from aeronexus.read_only_transport import ReadOnlyTransport
from aeronexus.status_runtime import StatusRuntime


PUBLIC = ProviderKind.PUBLIC_V2
ONPREM = ProviderKind.ONPREM_V2
PROJECT = "93df839d-ae74-4f04-842e-2f1f81c89a66"
ORG = "105ddd05-34ce-46b6-a872-cb32b8c98f64"
PC = ProviderConfig(PUBLIC, "https://es-flight-api-us.djigate.com", "not-a-real-token")
OC = ProviderConfig(ONPREM, "https://fh.example", "not-a-real-token")
RC = "5YSZM2B00X0000"
M4T = "1581F8HGX000TEST"

RC_MODEL = {"key": "2-174-0", "domain": "2", "type": "174", "sub_type": "0",
            "name": "DJI RC Plus 2", "class": "rc"}
M4T_MODEL = {"key": "0-99-1", "domain": "0", "type": "99", "sub_type": "1",
             "name": "Matrice 4T", "class": "drone"}
DOCK_MODEL = {"key": "3-3-0", "name": "DJI Dock 3", "class": "airport"}

M4T_STATE = {  # DeviceState_wa345, FlightHub string enums
    "latitude": 49.1, "longitude": 8.5, "height": 42.0, "elevation": 162.0,
    "home_distance": 120.0, "horizontal_speed": 5.0, "vertical_speed": 0.5,
    "mode_code": "manual_flight", "total_flight_time": 3600, "total_flight_sorties": 12,
    "position_state": {"gps_number": 20, "rtk_number": 31, "is_fixed": "fixing_successful",
                       "quality": "rtk_fixed"},
    "battery": {"capacity_percent": 81, "batteries": [
        {"index": "left_battery", "voltage": 16300, "temperature": 30.5, "capacity_percent": 81}]},
}
RC_STATE = {"capacity_percent": 64, "latitude": 49.1, "longitude": 8.5,
            "wireless_link": {"sdr_quality": 5}}


def public_devices():
    return {"code": 0, "message": "", "data": {"list": [
        {"gateway": {"sn": RC, "callsign": "RC Plus 2", "device_model": RC_MODEL,
                     "device_online_status": True, "mode_code": 0, "camera_list": []},
         "drone": {"sn": M4T, "callsign": "M4T Roman", "device_model": M4T_MODEL,
                   "device_online_status": True, "mode_code": 3, "camera_list": []}},
        {"gateway": {"sn": "DOCK1", "callsign": "Dock", "device_model": DOCK_MODEL,
                     "device_online_status": True, "mode_code": 0, "camera_list": []},
         "drone": None},
    ]}}


def state_payload(sn, state):
    return {"code": 0, "message": "", "data": {"device_sn": sn, "device_state": state}}


def topologies():
    def node(sn, model, state, **extra):
        return {"device_sn": sn, "device_model": model, "device_online_status": True,
                "is_device_pending_offline": False, "device_project_callsign": "",
                "device_organization_callsign": None, "device_state": state, **extra}
    return {"code": 0, "message": {"chinese": "", "english": ""}, "data": {"list": [
        {"index": "abc", "host": node(M4T, M4T_MODEL, M4T_STATE, device_project_callsign="M4T"),
         "parents": [node(RC, RC_MODEL, RC_STATE)], "nodes": []},
        {"index": "def", "host": None,
         "parents": [node("DOCK1", DOCK_MODEL, {}), node(RC, RC_MODEL, RC_STATE)], "nodes": []},
    ]}}


def hms_payload():
    return {"code": 0, "message": "", "data": {"list": [
        {"device_sn": M4T, "device_hms": {"list": [
            {"level": "notification", "code": "0x1", "message": "Info", "status": 1},
            {"level": "warning", "code": "0x16100083", "message": "Kompass kalibrieren",
             "status": 1, "imminent": True, "in_the_sky": "on_the_ground"},
            {"level": "warning", "code": "0x2", "message": "Vorbei", "status": 2},
        ]}},
        {"device_sn": "FOREIGN", "device_hms": {"list": [{"level": "warning", "status": 1}]}},
        {"device_sn": RC, "device_hms": None},
    ]}}


@pytest.fixture
def fake_get(monkeypatch):
    calls = []

    async def get(self, path, params=None, *, project_uuid=None):
        calls.append((path, project_uuid))
        if path == PUBLIC_PROJECT_DEVICES:
            assert params == {"device_model_class": "drone"}
            return public_devices()
        if path == f"/openapi/v2.0/device/{M4T}/state":
            return state_payload(M4T, M4T_STATE)
        if path == f"/openapi/v2.0/device/{RC}/state":
            return state_payload(RC, RC_STATE)
        if path == "/openapi/v2.0/organizations":
            return {"code": 0, "data": {"list": [{"uuid": ORG, "name": "Org",
                                                  "organization_id": "ABC123"}]}}
        if path == "/openapi/v2.0/device/hms":
            return hms_payload()
        if path.endswith("/topologies"):
            return topologies()
        if path == "/openapi/v2.0/project" or path.endswith("/projects"):
            return {"code": 0, "data": {"list": [{"uuid": PROJECT, "name": "Survey"}]}}
        raise AssertionError(path)
    monkeypatch.setattr(ReadOnlyTransport, "get", get)
    return calls


def test_public_list_imports_rc_and_aircraft_only():
    devices = normalize_public_project_devices(public_devices())
    assert [(d.kind, d.device_id, d.name, d.model) for d in devices] == [
        (DeviceType.CONTROLLER, RC, "RC Plus 2", "DJI RC Plus 2"),
        (DeviceType.AIRCRAFT, M4T, "M4T Roman", "Matrice 4T"),
    ]


def test_onprem_topology_dedupes_rc_and_skips_dock():
    devices = normalize_onprem_topologies(topologies())
    assert [(d.kind, d.device_id, d.name) for d in devices] == [
        (DeviceType.AIRCRAFT, M4T, "M4T"), (DeviceType.CONTROLLER, RC, "DJI RC Plus 2")]


def test_pending_offline_is_offline():
    payload = topologies()
    payload["data"]["list"][0]["host"]["is_device_pending_offline"] = True
    assert normalize_onprem_topologies(payload)[0].online is False


@pytest.mark.parametrize("payload", [
    None, {"code": 1, "data": {"list": []}}, {"code": 0, "data": {}},
    {"code": 0, "data": {"list": ["x"]}},
    {"code": 0, "data": {"list": [{"drone": {"device_model": M4T_MODEL}}]}},
    {"code": 0, "data": {"list": [{"drone": {"sn": "A", "device_model": M4T_MODEL,
                                             "device_online_status": "yes"}}]}},
    {"code": 0, "data": {"list": [{"gateway": {"sn": "A", "device_model": RC_MODEL},
                                   "drone": {"sn": "A", "device_model": M4T_MODEL}}]}},
])
def test_reject_malformed_public(payload):
    with pytest.raises(FleetError):
        normalize_public_project_devices(payload)


def test_public_fleet_reads_states_with_project_header(fake_get):
    fleet = dict((d.device_id, s) for d, s in asyncio.run(read_public_fleet(PC, PROJECT)))
    drone, rc = fleet[M4T], fleet[RC]
    assert drone.flight_mode_code == 3 and drone.elevation_m == 162.0
    assert drone.rtk_state == "is_fixed:fixing_successful" and drone.rtk_satellites == 31
    assert drone.battery_percent == 81 and drone.battery_voltage_mv == 16300
    assert drone.online is True
    assert rc.battery_percent == 64 and rc.online is True and rc.elevation_m is None
    assert all(project == PROJECT for _, project in fake_get)


def test_public_offline_device_skips_state_call(monkeypatch, fake_get):
    payload = public_devices()
    payload["data"]["list"][0]["drone"]["device_online_status"] = False
    async def get(self, path, params=None, *, project_uuid=None):
        if path == PUBLIC_PROJECT_DEVICES:
            return payload
        assert M4T not in path
        return state_payload(RC, RC_STATE)
    monkeypatch.setattr(ReadOnlyTransport, "get", get)
    fleet = dict((d.device_id, s) for d, s in asyncio.run(read_public_fleet(PC, PROJECT)))
    assert fleet[M4T].online is False and fleet[M4T].battery_percent is None


def test_public_state_for_other_device_rejected(monkeypatch):
    async def get(self, path, params=None, *, project_uuid=None):
        if path == PUBLIC_PROJECT_DEVICES:
            return public_devices()
        return state_payload("OTHER", RC_STATE)
    monkeypatch.setattr(ReadOnlyTransport, "get", get)
    with pytest.raises(FleetError):
        asyncio.run(read_public_fleet(PC, PROJECT))


def test_unknown_mode_string_is_none_not_error(fake_get):
    payload = topologies()
    payload["data"]["list"][0]["host"]["device_state"] = {**M4T_STATE, "mode_code": "future_mode"}
    devices = normalize_onprem_topologies(payload)
    assert snapshot(ONPREM, devices[0]).flight_mode_code is None


def test_zero_position_is_no_location():
    payload = topologies()
    payload["data"]["list"][0]["parents"][0]["device_state"] = {**RC_STATE, "latitude": 0, "longitude": 0}
    rc = [d for d in normalize_onprem_topologies(payload) if d.device_id == RC][0]
    assert snapshot(ONPREM, rc).latitude is None


def test_onprem_sync_into_registered_project(fake_get):
    inv = Inventory()
    inv.add_project(Project(ONPREM, PROJECT, "Survey"))
    assert asyncio.run(sync_project_fleet(inv, OC, PROJECT)) == (2, 2)
    kinds = {d.device_id: d.kind for d in inv.devices()}
    assert kinds == {M4T: DeviceType.AIRCRAFT, RC: DeviceType.CONTROLLER}
    assert fake_get == [(f"/openapi/v2.0/manage/api/v1/projects/{PROJECT}/topologies", PROJECT)]


def test_commit_requires_project_and_is_atomic(fake_get):
    fleet = asyncio.run(read_onprem_fleet(OC, PROJECT))
    with pytest.raises(FleetError):
        commit_fleet(Inventory(), ONPREM, PROJECT, fleet)
    inv = Inventory()
    inv.add_project(Project(ONPREM, PROJECT, "Survey"))
    bad = list(fleet) + [(fleet[0][0], fleet[0][1])]
    with pytest.raises(ValueError):
        commit_fleet(inv, ONPREM, PROJECT, tuple(bad))
    assert inv.devices() == ()


def test_callsign_change_renames_device(fake_get):
    inv = Inventory()
    inv.add_project(Project(ONPREM, PROJECT, "Survey"))
    asyncio.run(sync_project_fleet(inv, OC, PROJECT))
    payload = topologies()
    payload["data"]["list"][0]["host"]["device_project_callsign"] = "Neuer Name"
    commit_fleet(inv, ONPREM, PROJECT, tuple(
        (d, snapshot(ONPREM, d)) for d in normalize_onprem_topologies(payload)))
    assert {d.name for d in inv.devices()} == {"Neuer Name", "DJI RC Plus 2"}


def test_wrong_provider_and_uuid_rejected():
    with pytest.raises(FleetError):
        asyncio.run(read_public_fleet(OC, PROJECT))
    with pytest.raises(FleetError):
        asyncio.run(read_onprem_fleet(PC, PROJECT))
    with pytest.raises(FleetError):
        asyncio.run(read_onprem_fleet(OC, "../x"))


ENV = {"AERONEXUS_FH_POLL_ENABLED": "1", "AERONEXUS_DJI_PROVIDER": "public",
       "AERONEXUS_DJI_BASE_URL": "https://es-flight-api-us.djigate.com",
       "AERONEXUS_DJI_TOKEN": "secret-org-key"}


def test_poll_settings():
    assert FlightHubPollSettings.from_env({}) is None
    s = FlightHubPollSettings.from_env(ENV)
    assert s.interval_seconds == 30 and s.project_uuids == ()
    assert "secret-org-key" not in repr(s)
    for bad in ({"AERONEXUS_DJI_PROVIDER": "x"}, {"AERONEXUS_DJI_BASE_URL": "http://x"},
                {"AERONEXUS_DJI_TOKEN": ""}, {"AERONEXUS_FH_POLL_SECONDS": "5"},
                {"AERONEXUS_DJI_PROJECT_UUIDS": "nope"}, {"AERONEXUS_DJI_PROVIDER": "onprem"}):
        with pytest.raises(ValueError):
            FlightHubPollSettings.from_env({**ENV, **bad})
    onprem = FlightHubPollSettings.from_env({**ENV, "AERONEXUS_DJI_PROVIDER": "onprem",
                                             "AERONEXUS_DJI_ORGANIZATION_UUID": ORG})
    assert onprem.organization_uuid == ORG


def test_refresher_registers_projects_and_fleet(fake_get):
    runtime = StatusRuntime()
    refresher = FlightHubFleetRefresher(runtime, FlightHubPollSettings.from_env(ENV))
    asyncio.run(refresher())
    assert refresher.projects_synced == 1 and refresher.devices_synced == 2
    views = {v["device_id"]: v for v in runtime.device_views()}
    assert views[M4T]["freshness"] == "fresh" and views[RC]["kind"] == "controller"


def test_refresher_rejects_invisible_configured_project(fake_get):
    settings = FlightHubPollSettings.from_env(
        {**ENV, "AERONEXUS_DJI_PROJECT_UUIDS": "e7b81eec-f182-473a-9368-9e220e46f9d9"})
    with pytest.raises(ValueError):
        asyncio.run(FlightHubFleetRefresher(StatusRuntime(), settings)())


def test_app_starts_and_stops_poller(monkeypatch, fake_get):
    from fastapi.testclient import TestClient
    from aeronexus import app as app_module
    monkeypatch.setattr(app_module.app.state, "status_runtime", StatusRuntime())
    monkeypatch.delenv("AERONEXUS_CLOUD_MQTT_ENABLED", raising=False)
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    with TestClient(app_module.app) as client:
        for _ in range(50):
            body = client.get("/api/v1/status/summary").json()
            if body["registered_devices"]:
                break
            time.sleep(0.02)
        assert body["registered_devices"] == 2 and body["polling"] in ("idle", "running")
        assert "secret-org-key" not in str(body)
    assert app_module.app.state.status_runtime.polling == "stopped"


def test_poll_interval_validated():
    from aeronexus.status_polling import ReadOnlyStatusPoller
    async def refresh():
        return None
    with pytest.raises(ValueError):
        ReadOnlyStatusPoller(StatusRuntime(), refresh, interval_seconds=1)
    assert ReadOnlyStatusPoller(StatusRuntime(), refresh, interval_seconds=60).interval_seconds == 60


def test_probe_fleet_prints_counts_only(monkeypatch, capsys, fake_get):
    from aeronexus import probe_fleet
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("AERONEXUS_FH_POLL_ENABLED")
    assert probe_fleet.main() == 0
    out = capsys.readouterr().out
    assert "Aircraft: 1 (online 1" in out and "Remote controllers: 1 (online 1" in out
    for secret in (M4T, RC, "M4T Roman", "49.1", "secret-org-key", PROJECT):
        assert secret not in out


def test_probe_fleet_failure_hides_details(monkeypatch, capsys):
    from aeronexus import probe_fleet
    monkeypatch.setenv("AERONEXUS_DJI_PROVIDER", "public")
    monkeypatch.setenv("AERONEXUS_DJI_BASE_URL", "http://insecure")
    monkeypatch.setenv("AERONEXUS_DJI_TOKEN", "secret-org-key")
    assert probe_fleet.main() == 1
    assert "secret-org-key" not in capsys.readouterr().out


def test_hms_live_alerts_sorted_and_scoped():
    from aeronexus.flighthub_hms import normalize_hms
    result = normalize_hms(hms_payload(), [M4T, RC])
    assert set(result) == {M4T, RC} and result[RC] == ()
    assert [a["code"] for a in result[M4T]] == ["0x16100083", "0x1"]
    assert result[M4T][0] == {"level": "warning", "code": "0x16100083",
                              "message": "Kompass kalibrieren", "imminent": True,
                              "in_the_sky": False}


def test_hms_null_list_and_bad_payloads():
    from aeronexus.flighthub_hms import HmsError, normalize_hms
    assert normalize_hms({"code": 0, "data": {"list": None}}, [M4T]) == {M4T: ()}
    for bad in ({"code": 1}, {"code": 0, "data": {"list": "x"}}, {"code": 0},
                {"code": 0, "data": {"list": [1]}}):
        with pytest.raises(HmsError):
            normalize_hms(bad, [M4T])


def test_hms_rejects_unsafe_serial_and_onprem():
    from aeronexus.flighthub_hms import HmsError, read_public_hms
    with pytest.raises(HmsError):
        asyncio.run(read_public_hms(PC, PROJECT, ["../x"]))
    with pytest.raises(HmsError):
        asyncio.run(read_public_hms(OC, PROJECT, [M4T]))


def test_refresher_stores_health_and_summary_counts(fake_get):
    runtime = StatusRuntime()
    refresher = FlightHubFleetRefresher(runtime, FlightHubPollSettings.from_env(ENV))
    asyncio.run(refresher())
    assert refresher.hms_ok is True
    views = {v["device_id"]: v for v in runtime.device_views()}
    assert views[M4T]["health"][0]["level"] == "warning" and views[RC]["health"] == []
    assert runtime.summary()["health_warnings"] == 1
    assert ("/openapi/v2.0/device/hms", PROJECT) in fake_get


def test_hms_failure_keeps_telemetry(monkeypatch, fake_get):
    from aeronexus import flighthub_poller
    async def broken(*args, **kwargs):
        raise RuntimeError("HMS down")
    monkeypatch.setattr(flighthub_poller, "read_public_hms", broken)
    runtime = StatusRuntime()
    refresher = FlightHubFleetRefresher(runtime, FlightHubPollSettings.from_env(ENV))
    asyncio.run(refresher())
    assert refresher.hms_ok is False and refresher.devices_synced == 2
    assert runtime.health == {}


def test_region_and_api_version_settings():
    from aeronexus.providers import REGIONS
    assert FlightHubPollSettings.from_env({**ENV, "AERONEXUS_DJI_BASE_URL": ""}).config.base_url == REGIONS["eu"]
    us = FlightHubPollSettings.from_env({**ENV, "AERONEXUS_DJI_BASE_URL": "", "AERONEXUS_DJI_REGION": "us"})
    assert us.config.base_url == REGIONS["us"]
    old = FlightHubPollSettings.from_env({**ENV, "AERONEXUS_DJI_API_VERSION": "v0.1"})
    assert old.config.path("/project/device") == "/openapi/v0.1/project/device"
    for bad in ({"AERONEXUS_DJI_REGION": "mars", "AERONEXUS_DJI_BASE_URL": ""},
                {"AERONEXUS_DJI_API_VERSION": "v9"},
                {"AERONEXUS_DJI_PROVIDER": "onprem", "AERONEXUS_DJI_ORGANIZATION_UUID": ORG,
                 "AERONEXUS_DJI_API_VERSION": "v0.1"}):
        with pytest.raises(ValueError):
            FlightHubPollSettings.from_env({**ENV, **bad})


def test_v01_public_fleet_uses_v01_paths(monkeypatch):
    calls = []
    async def get(self, path, params=None, *, project_uuid=None):
        calls.append(path)
        if path == "/openapi/v0.1/project/device":
            return {"code": 0, "data": {"list": None}}
        raise AssertionError(path)
    monkeypatch.setattr(ReadOnlyTransport, "get", get)
    config = ProviderConfig(PUBLIC, "https://es-flight-api-eu.djigate.com", "k", "v0.1")
    assert asyncio.run(read_public_fleet(config, PROJECT)) == ()
    assert calls == ["/openapi/v0.1/project/device"]


def test_probe_fleet_401_hints_region(monkeypatch, capsys):
    from aeronexus import probe_fleet
    from aeronexus.read_only_transport import AuthenticationError
    async def get(self, path, params=None, *, project_uuid=None):
        raise AuthenticationError("DJI read-only request failed: HTTP 401",
                                  request_id="rid-1", status_code=401)
    monkeypatch.setattr(ReadOnlyTransport, "get", get)
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    assert probe_fleet.main() == 1
    out = capsys.readouterr().out
    assert "AERONEXUS_DJI_REGION" in out and "request_id=rid-1" in out
    assert "secret-org-key" not in out


def test_organization_code_check(fake_get):
    ok = FlightHubPollSettings.from_env({**ENV, "AERONEXUS_DJI_ORGANIZATION_ID": "abc123"})
    refresher = FlightHubFleetRefresher(StatusRuntime(), ok)
    asyncio.run(refresher())
    asyncio.run(refresher())
    assert refresher.organization_verified
    assert sum(path == "/openapi/v2.0/organizations" for path, _ in fake_get) == 1
    other = FlightHubPollSettings.from_env({**ENV, "AERONEXUS_DJI_ORGANIZATION_ID": "ZZZ999"})
    runtime = StatusRuntime()
    with pytest.raises(ValueError, match="does not belong"):
        asyncio.run(FlightHubFleetRefresher(runtime, other)())
    assert runtime.inventory.devices() == ()
    for bad in ("x", "has space", "../a"):
        with pytest.raises(ValueError):
            FlightHubPollSettings.from_env({**ENV, "AERONEXUS_DJI_ORGANIZATION_ID": bad})


def test_live_shape_aircraft_in_gateway_slot(fake_get):
    """Real EU gateway: Pilot 2 aircraft arrives as gateway (class drone), drone null."""
    payload = {"code": 0, "message": "", "data": {"list": [
        {"gateway": {"sn": M4T, "callsign": "", "device_model": M4T_MODEL,
                     "device_online_status": True, "mode_code": 0, "camera_list": []},
         "drone": None}]}}
    devices = normalize_public_project_devices(payload)
    assert [(d.kind, d.device_id, d.name) for d in devices] == [
        (DeviceType.AIRCRAFT, M4T, "Matrice 4T")]
