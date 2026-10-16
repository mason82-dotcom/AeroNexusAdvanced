"""Validated, read-only canonical DJI telemetry ingestion.

Coordinates are a pair; metric values are finite and within documented
physical bounds when known. No network access or flight commands.
"""
from collections.abc import Mapping
from math import isfinite

from .inventory import Inventory
from .providers import DeviceSnapshot, ProviderKind


class TelemetrySyncError(ValueError):
    pass


# Inclusive limits, or None where DJI does not publish a reliable bound.
_NUMERIC_FIELDS = {
    "latitude": (-90, 90),
    "longitude": (-180, 180),
    "battery_percent": (0, 100),
    "height_m": (None, None),
    "horizontal_speed_mps": (0, None),
    "vertical_speed_mps": (None, None),
    "total_flight_time_s": (0, None),
    "battery_voltage_mv": (0, None),
    "battery_temperature_c": (None, None),
}
_COUNT_FIELDS = frozenset({"total_flight_sorties", "rtk_satellites", "gps_satellites"})
_ALLOWED = frozenset({"device_id", "online", "rtk_state"}) | frozenset(_NUMERIC_FIELDS) | _COUNT_FIELDS


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
    for field, (lower, upper) in _NUMERIC_FIELDS.items():
        value = record.get(field)
        if value is not None:
            if type(value) not in (int, float):
                raise TelemetrySyncError(f"Invalid {field}")
            try:
                valid = (isfinite(value)
                         and (lower is None or value >= lower)
                         and (upper is None or value <= upper))
            except (TypeError, OverflowError, ValueError):
                valid = False
            if not valid:
                raise TelemetrySyncError(f"Out-of-range {field}")
        values[field] = value
    if (values["latitude"] is None) != (values["longitude"] is None):
        raise TelemetrySyncError("Coordinates must be supplied together")
    for field in _COUNT_FIELDS:
        value = record.get(field)
        if value is not None and (type(value) is not int or value < 0):
            raise TelemetrySyncError(f"Invalid {field}")
        values[field] = value
    rtk = record.get("rtk_state")
    if rtk is not None and (
        not isinstance(rtk, str) or not rtk.strip() or len(rtk) > 128
    ):
        raise TelemetrySyncError("Invalid RTK state")
    return DeviceSnapshot(
        provider=provider, device_id=device_id, online=online, rtk_state=rtk,
        **values,
    )


def register_snapshots(inventory: Inventory, project_id: str,
                       snapshots: tuple[DeviceSnapshot, ...]) -> int:
    """Preflight the entire batch before modifying the inventory."""
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
        # Also validate dataclass objects constructed outside parse_snapshot.
        data = {field: getattr(snapshot, field) for field in _ALLOWED}
        parse_snapshot(snapshot.provider, data)
    for snapshot in snapshots:
        inventory.update_telemetry(project_id, snapshot)
    return len(snapshots)
