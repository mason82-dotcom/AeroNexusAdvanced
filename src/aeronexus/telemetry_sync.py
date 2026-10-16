"""Read-only telemetry ingestion from normalized DJI adapter data.

No DJI wire format or network endpoint is assumed here.
"""
from collections.abc import Mapping
from math import isfinite
from .inventory import Inventory
from .providers import DeviceSnapshot, ProviderKind

class TelemetrySyncError(ValueError):
    pass

_ALLOWED = frozenset({"device_id", "online", "latitude", "longitude", "battery_percent", "rtk_state"})

def parse_snapshot(provider: ProviderKind, record: Mapping) -> DeviceSnapshot:
    if not isinstance(provider, ProviderKind) or not isinstance(record, Mapping):
        raise TelemetrySyncError("Invalid provider or telemetry record")
    if set(record) - _ALLOWED:
        raise TelemetrySyncError("Unknown telemetry fields")
    device_id = record.get("device_id")
    if not isinstance(device_id, str) or not device_id.strip():
        raise TelemetrySyncError("Invalid device ID")
    online = record.get("online")
    if online is not None and type(online) is not bool:
        raise TelemetrySyncError("Online must be boolean")
    values = {}
    for field, lower, upper in (("latitude", -90, 90), ("longitude", -180, 180),
                                 ("battery_percent", 0, 100)):
        value = record.get(field)
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, (float, int)):
                raise TelemetrySyncError(f"Invalid {field}")
            try:
                valid = isfinite(value) and lower <= value <= upper
            except (TypeError, OverflowError, ValueError):
                valid = False
            if not valid:
                raise TelemetrySyncError(f"Out-of-range {field}")
        values[field] = value
    if (values["latitude"] is None) != (values["longitude"] is None):
        raise TelemetrySyncError("Coordinates must be supplied together")
    rtk = record.get("rtk_state")
    if rtk is not None and (not isinstance(rtk, str) or not rtk.strip() or len(rtk) > 128):
        raise TelemetrySyncError("Invalid RTK state")
    return DeviceSnapshot(provider=provider, device_id=device_id, online=online,
                          rtk_state=rtk, **values)

def register_snapshots(inventory: Inventory, project_id: str,
                       snapshots: tuple[DeviceSnapshot, ...]) -> int:
    """Preflight entire batch before changing any inventory telemetry."""
    if not isinstance(inventory, Inventory) or not isinstance(project_id, str) or not project_id.strip():
        raise TelemetrySyncError("Invalid inventory or project")
    seen = set()
    for snapshot in snapshots:
        if not isinstance(snapshot, DeviceSnapshot) or not isinstance(snapshot.provider, ProviderKind):
            raise TelemetrySyncError("Invalid snapshot")
        key = (snapshot.provider, project_id, snapshot.device_id)
        if key in seen:
            raise TelemetrySyncError("Duplicate telemetry device")
        seen.add(key)
        if key not in inventory._devices:
            raise TelemetrySyncError("Telemetry references unknown device")
        # Validate even manually constructed snapshots.
        parse_snapshot(snapshot.provider, {
            "device_id": snapshot.device_id, "online": snapshot.online,
            "latitude": snapshot.latitude, "longitude": snapshot.longitude,
            "battery_percent": snapshot.battery_percent, "rtk_state": snapshot.rtk_state})
    for snapshot in snapshots:
        inventory.update_telemetry(project_id, snapshot)
    return len(snapshots)
