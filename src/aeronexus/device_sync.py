"""Validated device import boundary for DJI FlightHub providers.

Accepts canonical adapter records, not raw DJI API responses. No DJI
device-list endpoint is assumed until its wire schema is verified.
"""
from collections.abc import Mapping, Sequence
from .inventory import Device, DeviceType, Inventory
from .providers import ProviderKind

class DeviceSyncError(ValueError):
    pass

def parse_devices(provider: ProviderKind, project_id: str,
                  records: Sequence[Mapping]) -> tuple[Device, ...]:
    """Validate normalized adapter records and reject all unsupported types."""
    if not isinstance(provider, ProviderKind):
        raise DeviceSyncError("Invalid provider")
    if not isinstance(project_id, str) or not project_id.strip():
        raise DeviceSyncError("Invalid project ID")
    if isinstance(records, (str, bytes)) or not isinstance(records, (list, tuple)):
        raise DeviceSyncError("Device records must be a list")
    devices = []
    seen = set()
    for record in records:
        if not isinstance(record, Mapping):
            raise DeviceSyncError("Device record must be an object")
        kind = record.get("kind")
        if kind not in (DeviceType.AIRCRAFT.value, DeviceType.CONTROLLER.value):
            raise DeviceSyncError("Unsupported device type (including docks)")
        device_id = record.get("device_id")
        name = record.get("name")
        if not isinstance(device_id, str) or not isinstance(name, str):
            raise DeviceSyncError("Device ID and name must be strings")
        try:
            device = Device(provider, project_id, device_id, DeviceType(kind), name)
        except ValueError as exc:
            raise DeviceSyncError("Invalid device identity") from exc
        if device.device_id in seen:
            raise DeviceSyncError("Duplicate device ID in response")
        seen.add(device.device_id)
        devices.append(device)
    return tuple(devices)

def register_devices(inventory: Inventory, devices: tuple[Device, ...]) -> int:
    """Preflight all entries so validation errors never cause partial imports."""
    if not isinstance(inventory, Inventory):
        raise TypeError("Expected Inventory")
    seen = set()
    for device in devices:
        if not isinstance(device, Device):
            raise DeviceSyncError("Invalid device object")
        key = (device.provider, device.project_id, device.device_id)
        if key in seen:
            raise DeviceSyncError("Duplicate device in import")
        seen.add(key)
        if (device.provider, device.project_id) not in inventory._projects:
            raise DeviceSyncError("Project must exist before import")
        previous = inventory._devices.get(key)
        if previous is not None and previous != device:
            raise DeviceSyncError("Conflicting device identity")
    for device in devices:
        inventory.add_device(device)
    return len(devices)
