"""Local receive-time freshness and status summaries."""
from datetime import datetime, timedelta, timezone

import pytest

from aeronexus.inventory import Device, DeviceType, Inventory, Project
from aeronexus.providers import DeviceSnapshot, ProviderKind
from aeronexus.status_runtime import (
    StatusRuntime, StatusSettings, utc_iso,
)
from aeronexus.sync_pipeline import ingest_project_batch
from aeronexus.telemetry_sync import parse_snapshot, register_snapshots


K = ProviderKind.PUBLIC_V2
OTHER = ProviderKind.ONPREM_V2


def setup_runtime():
    inv = Inventory()
    inv.add_project(Project(K, "p", "Project"))
    inv.add_device(Device(K, "p", "a", DeviceType.AIRCRAFT, "Drone"))
    inv.add_device(Device(K, "p", "rc", DeviceType.CONTROLLER, "Controller"))
    return StatusRuntime(inv, StatusSettings(stale_after_seconds=90, refresh_every_seconds=30))


def test_missing_samples_are_not_online():
    rt = setup_runtime()
    result = rt.device_views()
    assert len(result) == 2
    assert all(x["freshness"] == "missing" and x["online"] is None for x in result)
    assert rt.summary()["missing"] == 2


def test_receive_timestamp_utc_and_freshness():
    rt = setup_runtime()
    snapshot = parse_snapshot(K, {"device_id": "a", "online": True,
                                  "latitude": 49.2, "longitude": 8.5,
                                  "battery_percent": 87})
    register_snapshots(rt.inventory, "p", (snapshot,))
    received = rt.inventory.telemetry_received_at(K, "p", "a")
    assert received is not None and received.tzinfo is not None
    view = rt.device_views(now=received + timedelta(seconds=15))[0]
    assert view["freshness"] == "fresh"
    assert view["age_seconds"] == 15
    assert view["online"] is True
    assert view["telemetry"]["battery_percent"] == 87
    assert view["received_at"].endswith("Z")


def test_stale_status_does_not_claim_online():
    rt = setup_runtime()
    rt.inventory.update_telemetry("p", DeviceSnapshot(K, "a", online=True))
    received = rt.inventory.telemetry_received_at(K, "p", "a")
    item = rt.device_views(now=received + timedelta(seconds=91))[0]
    assert item["freshness"] == "stale"
    assert item["online"] is None
    assert item["reported_online"] is True
    assert rt.summary(now=received + timedelta(seconds=91))["online_fresh"] == 0


def test_exact_threshold_is_fresh():
    rt = setup_runtime()
    rt.inventory.update_telemetry("p", DeviceSnapshot(K, "a", online=False))
    received = rt.inventory.telemetry_received_at(K, "p", "a")
    item = rt.device_views(now=received + timedelta(seconds=90))[0]
    assert item["freshness"] == "fresh"
    assert item["online"] is False


def test_clock_skew_is_not_fresh():
    rt = setup_runtime()
    rt.inventory.update_telemetry("p", DeviceSnapshot(K, "a", online=True))
    received = rt.inventory.telemetry_received_at(K, "p", "a")
    item = rt.device_views(now=received - timedelta(seconds=3))[0]
    assert item["freshness"] == "clock_skew"
    assert item["online"] is None


def test_unknown_timestamp_is_not_fresh():
    rt = setup_runtime()
    rt.inventory.update_telemetry("p", DeviceSnapshot(K, "a", online=True))
    rt.inventory._received_at.clear()
    item = rt.device_views()[0]
    assert item["freshness"] == "unknown_age"
    assert item["online"] is None


def test_missing_telemetry_does_not_reuse_timestamp():
    rt = setup_runtime()
    assert rt.inventory.telemetry_received_at(K, "p", "rc") is None


def test_summary_counts_only_not_identifiers():
    rt = setup_runtime()
    rt.inventory.update_telemetry("p", DeviceSnapshot(K, "a", online=True))
    s = rt.summary()
    assert (s["registered_devices"], s["aircraft"], s["controllers"]) == (2, 1, 1)
    assert s["online_fresh"] == 1
    assert s["missing"] == 1
    assert "device_id" not in s
    assert "latitude" not in s


def test_provider_project_scoping():
    rt = setup_runtime()
    rt.inventory.add_project(Project(OTHER, "p", "Second"))
    rt.inventory.add_device(Device(OTHER, "p", "a", DeviceType.AIRCRAFT, "Other Drone"))
    assert len(rt.device_views(K, "p")) == 2
    assert len(rt.device_views(OTHER, "p")) == 1
    assert len(rt.device_views(K, "missing")) == 0


def test_batch_copy_keeps_arrival_stamp_atomic():
    rt = setup_runtime()
    try:
        ingest_project_batch(rt.inventory, K, "p",
            [{"device_id": "new", "name": "New", "kind": "aircraft"}],
            [{"device_id": "new", "online": True},
             {"device_id": "not-registered", "online": True}])
    except ValueError:
        pass
    else:
        pytest.fail("Invalid batch accepted")
    assert rt.inventory.telemetry_received_at(K, "p", "new") is None
    assert all(d.device_id != "new" for d in rt.inventory.devices())


def test_batch_commit_includes_arrival_stamp():
    rt = setup_runtime()
    assert ingest_project_batch(rt.inventory, K, "p", [],
            [{"device_id": "a", "online": True}]) == (0, 1)
    assert rt.inventory.telemetry_received_at(K, "p", "a") is not None


def test_utc_iso_conversion():
    value = datetime(2026, 1, 1, 1, tzinfo=timezone(timedelta(hours=1)))
    assert utc_iso(value) == "2026-01-01T00:00:00Z"


def test_utc_iso_rejects_naive():
    with pytest.raises(ValueError):
        utc_iso(datetime(2026, 1, 1))


@pytest.mark.parametrize("stale,interval", [
    (True, 30), (4, 30), (86401, 30), (90, True),
    (90, 4), (90, 3601), (90, 30.5),
])
def test_invalid_settings(stale, interval):
    with pytest.raises(ValueError):
        StatusSettings(stale, interval)
