"""Atomic ingestion of normalized aircraft/controller inventory and telemetry.

This is a local ingestion pipeline, not a DJI wire decoder or API client.
"""
from collections.abc import Mapping, Sequence
from .device_sync import parse_devices, register_devices
from .inventory import Inventory
from .providers import ProviderKind
from .telemetry_sync import parse_snapshot, register_snapshots

class SyncPipelineError(ValueError):
    pass

def ingest_project_batch(inventory: Inventory, provider: ProviderKind,
                         project_id: str, devices: Sequence[Mapping],
                         telemetry: Sequence[Mapping]) -> tuple[int, int]:
    """Validate everything against a staging copy, then commit both maps.

    Existing snapshots for unaffected devices are preserved. Unknown telemetry
    devices and conflicting identities abort without changing inventory.
    """
    if not isinstance(inventory, Inventory):
        raise SyncPipelineError("Invalid inventory")
    if isinstance(telemetry, (str, bytes)) or not isinstance(telemetry, (list, tuple)):
        raise SyncPipelineError("Telemetry must be a list")
    # Stage against a copy to ensure device + telemetry changes are atomic.
    staging = Inventory(
        _projects=inventory._projects.copy(),
        _devices=inventory._devices.copy(),
        _telemetry=inventory._telemetry.copy(),
        _received_at=inventory._received_at.copy(),
    )
    parsed_devices = parse_devices(provider, project_id, devices)
    device_count = register_devices(staging, parsed_devices)
    snapshots = tuple(parse_snapshot(provider, item) for item in telemetry)
    snapshot_count = register_snapshots(staging, project_id, snapshots)
    inventory._devices.update(staging._devices)
    inventory._telemetry.update(staging._telemetry)
    inventory._received_at.update(staging._received_at)
    return device_count, snapshot_count
