"""Persistence, privacy and transition semantics of the DJI HMS history."""
from __future__ import annotations

import json
from collections import deque
from datetime import datetime, timezone

from fastapi.testclient import TestClient
import pytest

from aeronexus.app import app
from aeronexus.cloud_api_mqtt import CloudOsdIngest
from aeronexus.hms_history import HmsHistory
from aeronexus.providers import ProviderKind
from aeronexus.status_runtime import StatusRuntime

TOPIC_OSD = "thing/product/AC01/osd"
TOPIC_HMS = "thing/product/AC01/events"


def _setup(tmp_path):
    runtime = StatusRuntime(hms_history=HmsHistory(tmp_path / "private" / "hms.sqlite3"))
    ingest = CloudOsdIngest(runtime)
    assert ingest.handle(TOPIC_OSD, json.dumps({"data": {"mode_code": 3}}).encode())
    return runtime, ingest


def _hms(ingest, stamp, codes):
    alerts = [
        {"code": code, "level": 1, "module": 3, "device_type": "0-67-0"}
        for code in codes
    ]
    return ingest.handle_hms(
        TOPIC_HMS, json.dumps({"method": "hms", "timestamp": stamp,
                             "data": {"list": alerts}}).encode())


def test_appeared_resolved_reappeared_and_duplicate_suppression(tmp_path):
    runtime, ingest = _setup(tmp_path)
    ts = int(datetime.now(timezone.utc).timestamp() * 1000) - 2000
    a, b = "0x16070042", "0x1B0A0001"
    key = (ProviderKind.CLOUD_API, "aeronexus", "AC01")
    before = runtime.inventory.telemetry_received_at(*key)

    assert _hms(ingest, ts, [a, b])
    assert [x["action"] for x in runtime.hms_history.list_events()["events"]] == [
        "appeared", "appeared"
    ]
    assert _hms(ingest, ts + 1, [b])
    assert runtime.hms_history.list_events()["events"][0]["action"] == "resolved"
    assert runtime.hms_history.list_events()["events"][0]["code"] == a
    assert _hms(ingest, ts + 2, [a, b])
    assert runtime.hms_history.list_events()["events"][0]["action"] == "reappeared"
    assert not _hms(ingest, ts + 2, [])  # rejected as outdated, cannot clear
    assert _hms(ingest, ts + 3, [a, b])  # fresh snapshot, no state change
    assert runtime.hms_history.list_events()["total"] == 4
    assert runtime.inventory.telemetry_received_at(*key) == before

    disk = tmp_path / "private" / "hms.sqlite3"
    assert disk.stat().st_mode & 0o777 == 0o600
    persisted = HmsHistory(disk)
    data = persisted.list_events(device_id="AC01")
    assert data["persistent"] is True and data["total"] == 4
    assert [x["action"] for x in data["events"]] == [
        "reappeared", "resolved", "appeared", "appeared"
    ]
    assert "latitude" not in json.dumps(data)
    assert "device_secret" not in json.dumps(data)


def test_snapshot_restart_is_observed_not_false_reappeared(tmp_path):
    runtime, ingest = _setup(tmp_path)
    stamp = int(datetime.now(timezone.utc).timestamp() * 1000) - 2000
    code = "0x16070042"
    assert _hms(ingest, stamp, [code])
    new = StatusRuntime(hms_history=HmsHistory(tmp_path / "private" / "hms.sqlite3"))
    second = CloudOsdIngest(new)
    assert second.handle(TOPIC_OSD, b'{"data":{"mode_code":3}}')
    assert _hms(second, stamp + 1, [code])
    assert new.hms_history.list_events()["events"][0]["action"] == "observed"


def test_empty_snapshots_and_rejected_payloads_do_not_create_false_history(tmp_path):
    runtime, ingest = _setup(tmp_path)
    stamp = int(datetime.now(timezone.utc).timestamp() * 1000) - 2000
    assert _hms(ingest, stamp, [])
    assert runtime.hms_history.list_events()["total"] == 0
    assert not ingest.handle_hms(TOPIC_HMS, b'{"method":"not-hms","data":{"list":[]}}')
    assert runtime.hms_history.list_events()["total"] == 0


def test_history_pagination_retention_and_no_symlink_write(tmp_path):
    path = tmp_path / "timeline.sqlite3"
    history = HmsHistory(path, limit=3)
    device = (ProviderKind.CLOUD_API, "p", "AC01")
    t = datetime.now(timezone.utc)
    for i in range(5):
        alarm = {"code": f"0x1607004{i}", "device_domain": "aircraft",
                 "level": "reminder", "message": "DJI warning"}
        history.record_snapshot(device, (), (alarm,), t)
    assert history.list_events(limit=2)["total"] == 3
    assert len(HmsHistory(path, limit=3).events) == 3
    other = tmp_path / "target.sqlite3"
    other.write_text("untouched")
    symlink = tmp_path / "link.sqlite3"
    symlink.symlink_to(other)
    blocked = HmsHistory(symlink)
    assert blocked.storage_error
    blocked.record_snapshot(device, (), (alarm,), t)
    assert blocked.list_events()["total"] == 1
    assert blocked.list_events()["persistent"] is False
    assert other.read_text() == "untouched"


def test_hms_history_api_is_protected_and_bounded(tmp_path, monkeypatch):
    runtime, ingest = _setup(tmp_path)
    stamp = int(datetime.now(timezone.utc).timestamp() * 1000) - 2000
    assert _hms(ingest, stamp, ["0x16070042"])
    previous = app.state.status_runtime
    token = "hms-history-test-token-" + "x" * 32
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", token)
    app.state.status_runtime = runtime
    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/status/hms-history").status_code == 401
            headers = {"Authorization": "Bearer " + token}
            response = client.get(
                "/api/v1/status/hms-history?device_id=AC01&limit=5", headers=headers
            )
            assert response.status_code == 200
            assert response.headers.get("cache-control") == "no-store"
            body = response.json()
            assert body["total"] == 1 and body["events"][0]["action"] == "appeared"
            assert client.get("/api/v1/status/hms-history?limit=201",
                              headers=headers).status_code == 422
    finally:
        app.state.status_runtime = previous

def test_filtered_pagination_preserves_total_order_and_bounded_page():
    history = HmsHistory(limit=100)
    now = datetime.now(timezone.utc)
    for number in range(75):
        provider = ProviderKind.CLOUD_API if number % 3 else ProviderKind.PUBLIC_V2
        device = "AC01" if number % 2 else "RC02"
        history.record_snapshot(
            (provider, "project", device), (),
            ({"code": f"alarm-{number}", "device_domain": "aircraft",
              "level": "warning"},), now,
        )

    expected = [
        item for item in reversed(history.events)
        if item["provider"] == ProviderKind.CLOUD_API.value
        and item["device_id"] == "AC01"
    ]
    for offset, limit in ((0, 12), (5, 7), (19, 12), (1000, 20)):
        result = history.list_events(
            provider=ProviderKind.CLOUD_API.value,
            project_id="project", device_id="AC01",
            offset=offset, limit=limit,
        )
        assert result["total"] == len(expected)
        assert result["events"] == expected[offset:offset + limit]
        assert len(result["events"]) <= limit

    assert history.list_events(device_id="unknown")["events"] == []
    assert history.list_events(device_id="unknown")["total"] == 0

def test_device_history_index_prunes_evictions_and_survives_reload(tmp_path):
    path = tmp_path / "indexed-hms.sqlite3"
    history = HmsHistory(path, limit=3)
    now = datetime.now(timezone.utc)
    provider = ProviderKind.CLOUD_API
    for index, device in enumerate(("AC01", "RC01", "AC01", "AC02", "RC01")):
        history.record_snapshot(
            (provider, "project", device), (),
            ({"code": f"alarm-{index}", "device_domain": "aircraft",
              "level": "warning"},), now,
        )
    assert len(history.events) == 3
    assert history.list_events()["total"] == 3
    assert [e["code"] for e in history.list_events(
        provider=provider.value, project_id="project", device_id="AC01"
    )["events"]] == ["alarm-2"]
    assert history.list_events(
        provider=provider.value, project_id="project", device_id="RC01"
    )["events"][0]["code"] == "alarm-4"
    assert not history.list_events(
        provider=provider.value, project_id="project", device_id="unknown"
    )["events"]

    restored = HmsHistory(path, limit=3)
    assert restored.list_events() == history.list_events()
    for device in ("AC01", "RC01", "AC02"):
        assert restored.list_events(
            provider=provider.value, project_id="project", device_id=device
        )["events"] == history.list_events(
            provider=provider.value, project_id="project", device_id=device
        )["events"]


def test_device_history_query_never_scans_unrelated_global_events():
    history = HmsHistory(limit=5)
    now = datetime.now(timezone.utc)
    for number, device in enumerate(("A", "B", "C", "A", "B")):
        history.record_snapshot(
            (ProviderKind.CLOUD_API, "p", device), (),
            ({"code": str(number), "device_domain": "aircraft"},), now,
        )

    class GlobalScanForbidden(deque):
        def __reversed__(self):
            raise AssertionError("Device filtering scanned all HMS events")

    history.events = GlobalScanForbidden(history.events, maxlen=history.limit)
    result = history.list_events(
        provider=ProviderKind.CLOUD_API.value, project_id="p", device_id="A",
        limit=1, offset=1,
    )
    assert result["total"] == 2
    assert [item["code"] for item in result["events"]] == ["0"]
