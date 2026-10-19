"""Offline microbenchmark of the main read-only status and HMS hot paths.

Only synthetic in-memory inventory and HMS records. No credentials, MQTT,
FlightHub requests, SQLite files, network, systemd or DJI flight actions.
Results are development measurements, not production Pi performance claims.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from statistics import median
from time import perf_counter

from aeronexus.hms_history import HmsHistory
from aeronexus.inventory import Device, DeviceType, Project
from aeronexus.providers import DeviceSnapshot, ProviderKind
from aeronexus.status_runtime import StatusRuntime


PROVIDER = ProviderKind.CLOUD_API
PROJECT = "synthetic-benchmark"


def fixture(devices: int, events: int) -> StatusRuntime:
    runtime = StatusRuntime(hms_history=HmsHistory(limit=max(1, events)))
    runtime.inventory.add_project(Project(PROVIDER, PROJECT, "Synthetic project"))
    for index in range(devices):
        device_id = f"SYNTHETIC-{index:04d}"
        kind = DeviceType.AIRCRAFT if index % 2 == 0 else DeviceType.CONTROLLER
        runtime.inventory.add_device(Device(PROVIDER, PROJECT, device_id, kind, "Synthetic"))
        runtime.inventory.update_telemetry(
            PROJECT, DeviceSnapshot(PROVIDER, device_id,
                                    online=True, battery_percent=70))
    timestamp = datetime.now(timezone.utc)
    for index in range(events):
        device_id = f"SYNTHETIC-{index % devices:04d}"
        runtime.hms_history.record_snapshot(
            (PROVIDER, PROJECT, device_id), (),
            ({"code": f"synthetic-{index}", "device_domain": "aircraft",
              "level": "reminder"},), timestamp,
        )
    return runtime


def legacy_hms_page(history: HmsHistory, device_id: str, limit: int) -> dict:
    """Reference full scan equivalent to the pre-index device query."""
    selected = [
        item for item in reversed(history.events)
        if item["provider"] == PROVIDER.value
        and item["project_id"] == PROJECT
        and item["device_id"] == device_id
    ]
    return {"total": len(selected), "events": selected[:limit]}


def median_ms(callback, iterations: int) -> float:
    callback()  # warm caches and imports equally
    samples = []
    for _ in range(5):
        start = perf_counter()
        for _ in range(iterations):
            callback()
        samples.append((perf_counter() - start) * 1000.0 / iterations)
    return round(median(samples), 6)


def benchmark(devices: int = 40, events: int = 1600,
              iterations: int = 25) -> dict:
    if not (1 <= devices <= 300 and 0 <= events <= 10000
            and 1 <= iterations <= 500):
        raise ValueError("Benchmark fixture size is outside safe bounds")
    runtime = fixture(devices, events)
    now = datetime.now(timezone.utc)
    offset, limit = devices // 2, min(20, devices)
    device_id = f"SYNTHETIC-{offset:04d}"

    def full_projection():
        return runtime.device_views(now=now)[offset:offset + limit]

    def page_projection():
        return runtime.device_views(now=now, offset=offset, limit=limit)

    def full_history_scan():
        return legacy_hms_page(runtime.hms_history, device_id, 12)

    def indexed_history_query():
        result = runtime.hms_history.list_events(
            provider=PROVIDER.value, project_id=PROJECT, device_id=device_id,
            limit=12,
        )
        return {"total": result["total"], "events": result["events"]}

    if full_projection() != page_projection():
        raise AssertionError("Paged projection does not match old behavior")
    if full_history_scan() != indexed_history_query():
        raise AssertionError("Indexed HMS query does not match full scan")
    return {
        "fixture": "in-memory synthetic data only",
        "devices": devices, "hms_events": events, "iterations": iterations,
        "device_projection_full_ms": median_ms(full_projection, iterations),
        "device_projection_paged_ms": median_ms(page_projection, iterations),
        "hms_full_scan_ms": median_ms(full_history_scan, iterations),
        "hms_indexed_ms": median_ms(indexed_history_query, iterations),
        "result_equivalence": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--devices", type=int, default=40)
    parser.add_argument("--events", type=int, default=1600)
    parser.add_argument("--iterations", type=int, default=25)
    args = parser.parse_args()
    print(json.dumps(benchmark(args.devices, args.events, args.iterations),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
