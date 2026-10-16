import pytest
from aeronexus.inventory import Device, DeviceType, Inventory, Project
from aeronexus.providers import DeviceSnapshot, ProviderKind
from aeronexus.telemetry_sync import TelemetrySyncError, parse_snapshot, register_snapshots

K = ProviderKind.PUBLIC_V2

def inventory():
    i = Inventory()
    i.add_project(Project(K, "p", "Project"))
    i.add_device(Device(K, "p", "a", DeviceType.AIRCRAFT, "Drone"))
    return i

def test_parse_complete():
    s = parse_snapshot(K, {"device_id": "a", "online": True, "latitude": 49.1,
                            "longitude": 8.5, "battery_percent": 87, "rtk_state": "fixed"})
    assert s.battery_percent == 87 and s.rtk_state == "fixed"

def test_parse_partial():
    assert parse_snapshot(K, {"device_id": "a", "online": False}).latitude is None

@pytest.mark.parametrize("record", [
    {}, {"device_id": ""}, {"device_id": "a", "online": 1},
    {"device_id": "a", "latitude": 91, "longitude": 8},
    {"device_id": "a", "latitude": 50},
    {"device_id": "a", "longitude": 8},
    {"device_id": "a", "battery_percent": -1},
    {"device_id": "a", "battery_percent": float("nan")},
    {"device_id": "a", "latitude": float("inf"), "longitude": 1},
    {"device_id": "a", "battery_percent": True},
    {"device_id": "a", "rtk_state": ""},
    {"device_id": "a", "unknown": 123},
    "invalid", None
])
def test_reject_bad_snapshot(record):
    with pytest.raises(TelemetrySyncError):
        parse_snapshot(K, record)

def test_register_and_read():
    i = inventory()
    s = parse_snapshot(K, {"device_id": "a", "online": True})
    assert register_snapshots(i, "p", (s,)) == 1
    assert i.telemetry(K, "p", "a") == s

def test_unknown_device_batch_is_atomic():
    i = inventory()
    good = parse_snapshot(K, {"device_id": "a", "online": True})
    bad = parse_snapshot(K, {"device_id": "missing", "online": False})
    with pytest.raises(TelemetrySyncError):
        register_snapshots(i, "p", (good, bad))
    assert i.telemetry(K, "p", "a") is None

def test_duplicate_batch_is_atomic():
    i = inventory()
    s = parse_snapshot(K, {"device_id": "a"})
    with pytest.raises(TelemetrySyncError):
        register_snapshots(i, "p", (s, s))
    assert i.telemetry(K, "p", "a") is None

def test_manually_constructed_invalid_snapshot():
    i = inventory()
    s = DeviceSnapshot(K, "a", battery_percent=120)
    with pytest.raises(TelemetrySyncError):
        register_snapshots(i, "p", (s,))
