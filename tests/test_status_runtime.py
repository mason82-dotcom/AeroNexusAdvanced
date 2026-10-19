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

def test_summary_single_pass_preserves_all_freshness_and_warning_counts():
    rt = setup_runtime()
    for device_id in ("stale", "skew", "unknown", "missing"):
        rt.inventory.add_device(Device(K, "p", device_id, DeviceType.AIRCRAFT, device_id))
    now = datetime(2026, 10, 19, tzinfo=timezone.utc)
    for device_id, online in (("a", True), ("rc", False),
                              ("stale", True), ("skew", True), ("unknown", True)):
        rt.inventory.update_telemetry("p", DeviceSnapshot(K, device_id, online=online))
    for device_id, timestamp in (
        ("a", now - timedelta(seconds=5)),
        ("rc", now - timedelta(seconds=10)),
        ("stale", now - timedelta(seconds=91)),
        ("skew", now + timedelta(seconds=3)),
    ):
        rt.inventory._received_at[(K, "p", device_id)] = timestamp
    rt.inventory._received_at.pop((K, "p", "unknown"))
    rt.health[(K, "p", "a")] = ({"level": "warning"},)
    rt.health[(K, "p", "stale")] = ({"level": "info"},)

    summary = rt.summary(now=now)
    assert summary["registered_devices"] == 6
    assert (summary["aircraft"], summary["controllers"]) == (5, 1)
    assert {key: summary[key] for key in
            ("fresh", "stale", "missing", "unknown_age", "clock_skew")} == {
                "fresh": 2, "stale": 1, "missing": 1,
                "unknown_age": 1, "clock_skew": 1,
            }
    assert (summary["online_fresh"], summary["offline_fresh"]) == (1, 1)
    assert summary["health_warnings"] == 1
    assert "device_id" not in summary

def test_summary_omits_unused_per_device_hms_queries(monkeypatch):
    rt = setup_runtime()
    def forbid_history_lookup(**kwargs):
        raise AssertionError("Anonymous summary must not scan HMS device history")
    monkeypatch.setattr(rt.hms_history, "list_events", forbid_history_lookup)
    assert rt.summary()["registered_devices"] == 2
    # Detailed device responses still request device-local HMS history.
    with pytest.raises(AssertionError, match="must not scan"):
        rt.device_views()


def test_device_view_page_only_projects_selected_telemetry(monkeypatch):
    rt = setup_runtime()
    rt.inventory.update_telemetry("p", DeviceSnapshot(K, "a", online=True))
    rt.inventory.update_telemetry("p", DeviceSnapshot(K, "rc", online=False))
    scanned = []
    telemetry = rt.inventory.telemetry
    def counted(provider, project_id, device_id):
        scanned.append(device_id)
        return telemetry(provider, project_id, device_id)
    monkeypatch.setattr(rt.inventory, "telemetry", counted)
    page = rt.device_views(offset=1, limit=1)
    assert [row["device_id"] for row in page] == ["rc"]
    assert scanned == ["rc"]
    assert rt.device_views(offset=20, limit=1) == ()
    assert scanned == ["rc"]
    for offset, limit in ((-1, 1), (0, 0), (True, 1), (0, True)):
        with pytest.raises(ValueError, match="pagination"):
            rt.device_views(offset=offset, limit=limit)
