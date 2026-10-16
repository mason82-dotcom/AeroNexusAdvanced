"""DJI FlightHub 2 V2 read-only aircraft listing.

Field layouts and endpoints are based on DJI's official
FlightHub-2-OpenAPI-V2-Demo (PublicCloud/DeviceList and
Privatization/DeviceList). Infrastructure records are never imported.

On-premises results expose an active project *name*, not a verified project
UUID in the official demo. Those observations are not auto-assigned to projects.
"""
from dataclasses import dataclass
from collections.abc import Mapping
from uuid import UUID

from .providers import ProviderConfig, ProviderKind
from .read_only_transport import ReadOnlyTransport
from .sync_pipeline import ingest_project_batch
from .inventory import Inventory
from .telemetry_sync import parse_snapshot


PUBLIC_LIST = "/openapi/v2.0/project/device"


@dataclass(frozen=True)
class ObservedAircraft:
    device_id: str
    name: str
    online: bool | None
    battery_percent: int | float | None = None
    latitude: int | float | None = None
    longitude: int | float | None = None
    rtk_state: str | None = None
    project_name: str | None = None

    def records(self) -> tuple[dict, dict]:
        device = {"kind": "aircraft", "device_id": self.device_id, "name": self.name}
        telemetry = {
            "device_id": self.device_id, "online": self.online,
            "battery_percent": self.battery_percent,
            "latitude": self.latitude, "longitude": self.longitude,
            "rtk_state": self.rtk_state,
        }
        return device, telemetry


class DeviceListError(ValueError):
    pass


def _uuid(value: str) -> str:
    if not isinstance(value, str):
        raise DeviceListError("UUID must be a string")
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise DeviceListError("Invalid UUID") from exc


def _list(payload: Mapping) -> list:
    data = payload.get("data") if isinstance(payload, Mapping) else None
    records = data.get("list") if isinstance(data, Mapping) else None
    if not isinstance(records, list):
        raise DeviceListError("Invalid DJI device list payload")
    return records


def _online(value, *, public: bool) -> bool | None:
    if value is None or type(value) is bool:
        return value
    if public and type(value) is int and value in (0, 1):
        return bool(value)
    raise DeviceListError("Unrecognized device online status")


def _state(record: Mapping) -> Mapping:
    state = record.get("device_state")
    if state is None:
        return {}
    if not isinstance(state, Mapping):
        raise DeviceListError("Invalid device state")
    return state


def _battery(state: Mapping):
    maintenance = state.get("drone_battery_maintenance_info")
    if isinstance(maintenance, Mapping):
        batteries = maintenance.get("batteries")
        if isinstance(batteries, list) and batteries and isinstance(batteries[0], Mapping):
            value = batteries[0].get("capacity_percent")
            if value is not None:
                return value
    for name in ("drone_charge_state", "battery"):
        branch = state.get(name)
        if isinstance(branch, Mapping) and branch.get("capacity_percent") is not None:
            return branch["capacity_percent"]
    return None


def _observation(record: Mapping, provider: ProviderKind, *, public: bool,
                 project_name: str | None = None) -> ObservedAircraft:
    sn = record.get("sn") if public else record.get("device_sn")
    if not sn:
        sn = record.get("device_sn") if public else None
    if not isinstance(sn, str) or not sn.strip():
        raise DeviceListError("Missing aircraft serial number")
    model = record.get("device_model")
    if model is not None and not isinstance(model, Mapping):
        raise DeviceListError("Invalid device model")
    callsign = record.get("callsign") if public else record.get("device_callsign")
    if not callsign:
        callsign = record.get("device_callsign") if public else None
    model_name = model.get("name") if isinstance(model, Mapping) else None
    name = callsign if isinstance(callsign, str) and callsign.strip() else (
        model_name if isinstance(model_name, str) and model_name.strip() else sn
    )
    state = _state(record)
    data = {
        "device_id": sn,
        "online": _online(record.get("device_online_status"), public=public),
        "battery_percent": _battery(state),
        "latitude": state.get("latitude"),
        "longitude": state.get("longitude"),
        "rtk_state": state.get("rtk_state"),
    }
    # Reuse the strict canonical schema to reject invalid telemetry.
    snapshot = parse_snapshot(provider, data)
    return ObservedAircraft(
        device_id=sn, name=name, online=snapshot.online,
        battery_percent=snapshot.battery_percent, latitude=snapshot.latitude,
        longitude=snapshot.longitude, rtk_state=snapshot.rtk_state,
        project_name=project_name,
    )


def normalize_public_topology(payload: Mapping) -> tuple[ObservedAircraft, ...]:
    """Select only the 'drone' child of each {gateway, drone} topology row."""
    result = []
    seen = set()
    for item in _list(payload):
        if not isinstance(item, Mapping):
            raise DeviceListError("Invalid topology entry")
        drone = item.get("drone")
        if drone is None:
            continue
        if not isinstance(drone, Mapping):
            raise DeviceListError("Invalid aircraft topology")
        model = drone.get("device_model")
        if isinstance(model, Mapping) and model.get("class") not in (None, "drone"):
            continue
        obs = _observation(drone, ProviderKind.PUBLIC_V2, public=True)
        if obs.device_id in seen:
            raise DeviceListError("Duplicate aircraft in topology")
        seen.add(obs.device_id)
        result.append(obs)
    return tuple(result)


def normalize_onprem_page(payload: Mapping) -> tuple[ObservedAircraft, ...]:
    """The documented On-Premises list is filtered to device_model_class=drone."""
    result = []
    seen = set()
    for item in _list(payload):
        if not isinstance(item, Mapping):
            raise DeviceListError("Invalid device list entry")
        model = item.get("device_model")
        if not isinstance(model, Mapping) or model.get("class") != "drone":
            continue
        project_name = item.get("device_active_project_name")
        if project_name is not None and not isinstance(project_name, str):
            raise DeviceListError("Invalid active project name")
        obs = _observation(item, ProviderKind.ONPREM_V2, public=False,
                           project_name=project_name)
        if obs.device_id in seen:
            raise DeviceListError("Duplicate aircraft in page")
        seen.add(obs.device_id)
        result.append(obs)
    return tuple(result)


async def read_public_aircraft(config: ProviderConfig, project_uuid: str) -> tuple[ObservedAircraft, ...]:
    """GET the Public Cloud project topology with a validated project header."""
    if config.kind != ProviderKind.PUBLIC_V2:
        raise DeviceListError("Public Cloud provider required")
    project_uuid = _uuid(project_uuid)
    client = ReadOnlyTransport(config, frozenset({PUBLIC_LIST}))
    payload = await client.get(PUBLIC_LIST, project_uuid=project_uuid)
    return normalize_public_topology(payload)


async def read_onprem_aircraft(config: ProviderConfig, organization_uuid: str, *,
                              page: int = 1, page_size: int = 20) -> tuple[ObservedAircraft, ...]:
    """GET one organization-wide On-Premises aircraft page, without project assignment."""
    if config.kind != ProviderKind.ONPREM_V2:
        raise DeviceListError("On-Premises provider required")
    organization_uuid = _uuid(organization_uuid)
    if type(page) is not int or type(page_size) is not int or not (1 <= page <= 100000 and 1 <= page_size <= 100):
        raise DeviceListError("Invalid pagination")
    path = f"/openapi/v2.0/manage/api/v1/organizations/{organization_uuid}/manage-devices"
    client = ReadOnlyTransport(config, frozenset({path}))
    payload = await client.get(path, {
        "device_model_class": "drone", "page": page, "page_size": page_size,
    })
    return normalize_onprem_page(payload)


async def sync_public_aircraft(inventory: Inventory, config: ProviderConfig,
                               project_uuid: str) -> tuple[int, int]:
    """Read and import only aircraft from a caller-selected registered Public project."""
    if not isinstance(inventory, Inventory):
        raise TypeError("Inventory required")
    project_uuid = _uuid(project_uuid)
    if (ProviderKind.PUBLIC_V2, project_uuid) not in inventory._projects:
        raise DeviceListError("Project must be registered before sync")
    observations = await read_public_aircraft(config, project_uuid)
    device_records, telemetry_records = [], []
    for observation in observations:
        device, telemetry = observation.records()
        device_records.append(device)
        telemetry_records.append(telemetry)
    # Existing atomic staging logic prevents partial imports.
    return ingest_project_batch(inventory, ProviderKind.PUBLIC_V2, project_uuid,
                                device_records, telemetry_records)
