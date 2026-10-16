"""Project-scoped FlightHub 2 V2 fleet (aircraft + remote controllers), read-only.

Endpoints per the official OpenAPI V2.0 specifications (Apifox, 2026):
  Public Cloud
    GET /openapi/v2.0/project/device          rows of {gateway, drone}
    GET /openapi/v2.0/device/{device_sn}/state thing model snapshot
  On-Premises
    GET /openapi/v2.0/manage/api/v1/projects/{proj_uuid}/topologies
        rows of {host (aircraft), parents (RC / dock / ...), nodes (relays)}
        including device_state, online status and project call sign.

Only device_model.class "drone" (aircraft) and "rc" (remote controller) are
imported; docks ("airport"), relays, base stations and payloads are skipped.

Observed on the live EU gateway (2026-10-16, Matrice 4T + RC Plus 2 via
Pilot 2): the Public list answers {"list": null} unless device_model_class
is given ("rc" is rejected with code 210070), and an RC-connected aircraft
is reported in the "gateway" slot (class drone) with "drone": null. The RC
itself is not listed. Classification is therefore by device_model.class,
not by slot.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from .flighthub_device_state import (DeviceStateError, normalize_aircraft_state,
                                     normalize_controller_state)
from .inventory import Device, DeviceType, Inventory
from .providers import DeviceSnapshot, ProviderConfig, ProviderKind
from .read_only_transport import ReadOnlyTransport
from .sync_pipeline import ingest_project_batch


PUBLIC_PROJECT_DEVICES = "/openapi/v2.0/project/device"
_KINDS = {"drone": DeviceType.AIRCRAFT, "rc": DeviceType.CONTROLLER}
MAX_DEVICES_PER_PROJECT = 50


class FleetError(ValueError):
    pass


@dataclass(frozen=True)
class FleetDevice:
    kind: DeviceType
    device_id: str
    name: str
    model: str | None
    online: bool | None
    state: Mapping | None = None


def _uuid(value) -> str:
    if not isinstance(value, str):
        raise FleetError("Invalid UUID")
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise FleetError("Invalid UUID") from exc


def _data(payload) -> Mapping:
    if not isinstance(payload, Mapping) or type(payload.get("code")) is not int or payload["code"] != 0:
        raise FleetError("Unsuccessful FlightHub response")
    data = payload.get("data")
    # FlightHub returns {"list": null} for empty collections (verified live by
    # dji-flighthub2-cli), not [].
    if isinstance(data, Mapping) and data.get("list", ...) is None:
        return {**data, "list": []}
    if not isinstance(data, Mapping) or not isinstance(data.get("list"), list):
        raise FleetError("Missing FlightHub device list")
    return data


def _model(record: Mapping) -> tuple[str | None, str | None]:
    model = record.get("device_model")
    if model is None:
        return None, None
    if not isinstance(model, Mapping):
        raise FleetError("Invalid device model")
    cls, name = model.get("class"), model.get("name")
    return (cls if isinstance(cls, str) else None,
            name if isinstance(name, str) and name.strip() else None)


def _text(*values) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _online(value) -> bool | None:
    if value is None or type(value) is bool:
        return value
    if type(value) is int and value in (0, 1):
        return bool(value)
    raise FleetError("Unsupported online status")


def _entry(record, serial_key: str, *callsign_keys: str) -> FleetDevice | None:
    if record is None:
        return None
    if not isinstance(record, Mapping):
        raise FleetError("Invalid device entry")
    cls, model = _model(record)
    kind = _KINDS.get(cls)
    if kind is None:
        return None
    serial = record.get(serial_key)
    if not isinstance(serial, str) or not serial.strip():
        raise FleetError("Missing device serial number")
    online = _online(record.get("device_online_status"))
    if online is True and record.get("is_device_pending_offline") is True:
        online = False  # On-Premises offline grace period
    state = record.get("device_state")
    if state is not None and not isinstance(state, Mapping):
        raise FleetError("Invalid device state")
    name = _text(*(record.get(key) for key in callsign_keys), model, serial)
    return FleetDevice(kind, serial, name, model, online, state)


def _unique(devices) -> tuple[FleetDevice, ...]:
    result, seen = [], {}
    for device in devices:
        if device is None:
            continue
        if device.device_id in seen:
            if seen[device.device_id] != device.kind:
                raise FleetError("Device listed with conflicting types")
            continue  # an RC can appear in several topology rows
        seen[device.device_id] = device.kind
        result.append(device)
    if len(result) > MAX_DEVICES_PER_PROJECT:
        raise FleetError("Too many devices in project")
    return tuple(result)


def normalize_public_project_devices(payload) -> tuple[FleetDevice, ...]:
    devices = []
    for row in _data(payload)["list"]:
        if not isinstance(row, Mapping):
            raise FleetError("Invalid topology row")
        devices.append(_entry(row.get("gateway"), "sn", "callsign"))
        devices.append(_entry(row.get("drone"), "sn", "callsign"))
    return _unique(devices)


def normalize_onprem_topologies(payload) -> tuple[FleetDevice, ...]:
    devices = []
    callsigns = ("device_project_callsign", "device_organization_callsign")
    for row in _data(payload)["list"]:
        if not isinstance(row, Mapping):
            raise FleetError("Invalid topology row")
        devices.append(_entry(row.get("host"), "device_sn", *callsigns))
        parents = row.get("parents") or []
        if not isinstance(parents, list):
            raise FleetError("Invalid topology parents")
        devices.extend(_entry(parent, "device_sn", *callsigns) for parent in parents)
    return _unique(devices)


def snapshot(provider: ProviderKind, device: FleetDevice, state: Mapping | None = None) -> DeviceSnapshot:
    state = device.state if state is None else state
    try:
        if device.kind == DeviceType.AIRCRAFT:
            return normalize_aircraft_state(provider, device.device_id, state or {},
                                            online_override=device.online)
        return normalize_controller_state(provider, device.device_id, state or {},
                                          online=device.online)
    except DeviceStateError as exc:
        raise FleetError("Invalid device state") from exc


async def read_public_fleet(config: ProviderConfig, project_uuid: str, *,
                            with_state: bool = True) -> tuple[tuple[FleetDevice, DeviceSnapshot], ...]:
    """Project device list, then one state GET per online aircraft/RC (bounded).

    Offline devices keep the list information only; their thing model is not
    requested.
    """
    if config.kind != ProviderKind.PUBLIC_V2:
        raise FleetError("Public Cloud provider required")
    project_uuid = _uuid(project_uuid)
    list_path = config.path("/project/device")
    listing = ReadOnlyTransport(config, frozenset({list_path}))
    devices = normalize_public_project_devices(
        await listing.get(list_path, {"device_model_class": "drone"}, project_uuid=project_uuid))
    result = []
    for device in devices:
        state = None
        if with_state and device.online is not False:
            path = config.path(f"/device/{device.device_id}/state")
            payload = await ReadOnlyTransport(config, frozenset({path})).get(
                path, project_uuid=project_uuid)
            data = payload.get("data")
            if not isinstance(data, Mapping) or data.get("device_sn", device.device_id) != device.device_id:
                raise FleetError("State belongs to a different device")
            state = data.get("device_state", {})
            if not isinstance(state, Mapping):
                raise FleetError("Invalid device state")
        result.append((device, snapshot(ProviderKind.PUBLIC_V2, device, state)))
    return tuple(result)


async def read_onprem_fleet(config: ProviderConfig, project_uuid: str
                            ) -> tuple[tuple[FleetDevice, DeviceSnapshot], ...]:
    """Single topology GET; thing model state is embedded per device."""
    if config.kind != ProviderKind.ONPREM_V2:
        raise FleetError("On-Premises provider required")
    project_uuid = _uuid(project_uuid)
    path = f"/openapi/v2.0/manage/api/v1/projects/{project_uuid}/topologies"
    payload = await ReadOnlyTransport(config, frozenset({path})).get(path, project_uuid=project_uuid)
    return tuple((device, snapshot(ProviderKind.ONPREM_V2, device))
                 for device in normalize_onprem_topologies(payload))


def commit_fleet(inventory: Inventory, provider: ProviderKind, project_uuid: str,
                 fleet: tuple[tuple[FleetDevice, DeviceSnapshot], ...]) -> tuple[int, int]:
    """Atomic import; a changed FlightHub call sign renames the local device."""
    if not isinstance(inventory, Inventory):
        raise TypeError("Inventory required")
    project_uuid = _uuid(project_uuid)
    if (provider, project_uuid) not in inventory._projects:
        raise FleetError("Project must be registered before sync")
    staging = Inventory(
        _projects=inventory._projects.copy(), _devices=inventory._devices.copy(),
        _telemetry=inventory._telemetry.copy(), _received_at=inventory._received_at.copy())
    for device, _ in fleet:
        key = (provider, project_uuid, device.device_id)
        known = staging._devices.get(key)
        if known is not None and known.kind != device.kind:
            raise FleetError("Device type changed")
        if known is not None and known.name != device.name:
            staging._devices[key] = Device(provider, project_uuid, device.device_id,
                                           device.kind, device.name)
    counts = ingest_project_batch(
        staging, provider, project_uuid,
        [{"kind": d.kind.value, "device_id": d.device_id, "name": d.name} for d, _ in fleet],
        [{key: value for key, value in vars(s).items() if key != "provider"} for _, s in fleet])
    inventory._devices.update(staging._devices)
    inventory._telemetry.update(staging._telemetry)
    inventory._received_at.update(staging._received_at)
    return counts


async def sync_project_fleet(inventory: Inventory, config: ProviderConfig,
                             project_uuid: str) -> tuple[int, int]:
    if config.kind == ProviderKind.PUBLIC_V2:
        fleet = await read_public_fleet(config, project_uuid)
    elif config.kind == ProviderKind.ONPREM_V2:
        fleet = await read_onprem_fleet(config, project_uuid)
    else:
        raise FleetError("FlightHub V2 provider required")
    return commit_fleet(inventory, config.kind, project_uuid, fleet)
