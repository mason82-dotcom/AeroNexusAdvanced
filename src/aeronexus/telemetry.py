"""Strict, transport-neutral telemetry normalization."""
from math import isfinite
from typing import Any
from .providers import DeviceSnapshot, ProviderKind

def _optional_float(value: Any, minimum: float, maximum: float) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Numeric telemetry field has invalid type")
    number = float(value)
    if not isfinite(number) or not minimum <= number <= maximum:
        raise ValueError("Numeric telemetry field out of range")
    return number

def normalize_snapshot(provider: ProviderKind, payload: dict[str, Any]) -> DeviceSnapshot:
    """Normalize internal canonical payload; not a DJI wire-format decoder."""
    if not isinstance(payload, dict):
        raise ValueError("Telemetry payload must be an object")
    device_id = payload.get("device_id")
    if not isinstance(device_id, str) or not device_id.strip():
        raise ValueError("device_id is required")
    online = payload.get("online")
    if online is not None and not isinstance(online, bool):
        raise ValueError("online must be boolean or null")
    rtk = payload.get("rtk_state")
    if rtk is not None and not isinstance(rtk, str):
        raise ValueError("rtk_state must be string or null")
    return DeviceSnapshot(
        provider=provider, device_id=device_id, online=online,
        latitude=_optional_float(payload.get("latitude"), -90, 90),
        longitude=_optional_float(payload.get("longitude"), -180, 180),
        battery_percent=_optional_float(payload.get("battery_percent"), 0, 100),
        rtk_state=rtk)
