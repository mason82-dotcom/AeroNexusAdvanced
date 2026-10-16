"""DJI FlightHub V2 detailed aircraft status, read-only.

Sources: dji-sdk/FlightHub-2-OpenAPI-V2-Demo
  PublicCloud/DeviceList/main.ts: GET /openapi/v2.0/device/{sn}/state
  Privatization/DeviceList/main.ts: device_state embedded in manage-devices

An RTK satellite count is NOT an RTK fix. position_state.is_fixed is
retained as a raw, explicitly labelled value, not interpreted as a fix.
"""
from collections.abc import Mapping
from dataclasses import replace
import re
from uuid import UUID

from .flighthub_device_list import _battery
from .inventory import DeviceType, Inventory
from .providers import DeviceSnapshot, ProviderConfig, ProviderKind
from .read_only_transport import ReadOnlyTransport
from .telemetry_sync import parse_snapshot, register_snapshots


class DeviceStateError(ValueError):
    pass


_SERIAL = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
_ONLINE = {
    "online": True,
    "power_on": True,
    "offline": False,
    "power_off": False,
}


# Aircraft mode_code: FlightHub V2 thing models report the documented string
# enum, DJI Cloud API reports the integer. Same order, index = DJI code.
_MODE_CODES = (
    "standby", "takeoff_preparation", "takeoff_preparation_completed",
    "manual_flight", "automatic_takeoff", "wayline_flight",
    "panoramic_photography", "intelligent_tracking", "adsb_avoidance",
    "auto_returning_to_home", "automatic_landing", "forced_landing",
    "three_blade_landing", "upgrading", "not_connected", "apas",
    "virtual_stick_state", "live_flight_controls", "airborne_rtk_fixing_mode",
    "dock_address_selecting",
)


def _mode_code(value) -> int | None:
    """Unknown future enum strings become None instead of discarding the sample."""
    if value is None:
        return None
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str):
        return _MODE_CODES.index(value) if value in _MODE_CODES else None
    raise DeviceStateError("Invalid mode code")


def _serial(value: str) -> str:
    if not isinstance(value, str) or _SERIAL.fullmatch(value) is None:
        raise DeviceStateError("Invalid aircraft serial number")
    return value


def _uuid(value: str) -> str:
    if not isinstance(value, str):
        raise DeviceStateError("Invalid UUID")
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise DeviceStateError("Invalid UUID") from exc


def _online(value) -> bool | None:
    if value is None or type(value) is bool:
        return value
    if type(value) is int and value in (0, 1):
        return bool(value)
    if isinstance(value, str) and value in _ONLINE:
        return _ONLINE[value]
    raise DeviceStateError("Unsupported online status")


def _branch(data: Mapping, field: str) -> Mapping:
    value = data.get(field)
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise DeviceStateError(f"Invalid {field} structure")
    return value


def _rtk_raw(position: Mapping, state: Mapping) -> str | None:
    """Do not infer RTK fixed/float from satellite count or numeric flags."""
    raw = position.get("is_fixed")
    if raw is None:
        raw = state.get("rtk_state")
        if raw is None:
            return None
        if not isinstance(raw, str) or not raw.strip():
            raise DeviceStateError("Invalid RTK state")
        return raw
    if type(raw) not in (str, int):
        raise DeviceStateError("Invalid RTK fixed-state code")
    if isinstance(raw, str) and not raw.strip():
        raise DeviceStateError("Invalid RTK fixed-state code")
    return f"is_fixed:{raw}"


def _battery_info(state: Mapping) -> tuple[object, object]:
    """Voltage (mV) and temperature (C) from the first documented battery."""
    battery = _branch(state, "battery")
    if "voltage" in battery or "temperature" in battery:
        return battery.get("voltage"), battery.get("temperature")
    batteries = battery.get("batteries")
    if batteries is None:
        batteries = _branch(state, "drone_battery_maintenance_info").get("batteries")
    if isinstance(batteries, list) and batteries and isinstance(batteries[0], Mapping):
        return batteries[0].get("voltage"), batteries[0].get("temperature")
    return None, None


def normalize_aircraft_state(
    provider: ProviderKind, device_id: str, state: Mapping,
    *, online_override=None,
) -> DeviceSnapshot:
    """Translate verified DJI device-state field names to canonical telemetry.

    Missing values stay None. No assumption is made about a GPS fix or RTK
    quality when the source lacks an explicit status.
    """
    if provider not in (ProviderKind.PUBLIC_V2, ProviderKind.ONPREM_V2):
        raise DeviceStateError("FlightHub V2 provider required")
    _serial(device_id)
    if not isinstance(state, Mapping):
        raise DeviceStateError("Device state must be an object")
    for key in ("device_sn", "sn"):
        if key in state and state[key] != device_id:
            raise DeviceStateError("State belongs to a different aircraft")
    position = _branch(state, "position_state")
    voltage, temperature = _battery_info(state)
    raw_online = state.get("device_online_status", online_override)
    latitude, longitude = _position(state)
    return parse_snapshot(provider, {
        "device_id": device_id,
        "online": _online(raw_online),
        "latitude": latitude,
        "longitude": longitude,
        "battery_percent": _battery(state),
        "rtk_state": _rtk_raw(position, state),
        "height_m": state.get("height"),
        "horizontal_speed_mps": state.get("horizontal_speed"),
        "vertical_speed_mps": state.get("vertical_speed"),
        "total_flight_time_s": state.get("total_flight_time"),
        "total_flight_sorties": state.get("total_flight_sorties"),
        "rtk_satellites": position.get("rtk_number"),
        "gps_satellites": position.get("gps_number"),
        "battery_voltage_mv": voltage,
        "battery_temperature_c": temperature,
        "elevation_m": state.get("elevation"),
        "home_distance_m": state.get("home_distance"),
        "flight_mode_code": _mode_code(state.get("mode_code")),
    })


def _position(state: Mapping) -> tuple[object, object]:
    """DJI reports 0/0 when no position is known; that is not a location."""
    latitude, longitude = state.get("latitude"), state.get("longitude")
    if latitude == 0 and longitude == 0 and type(latitude) is not bool and type(longitude) is not bool:
        return None, None
    return latitude, longitude


def normalize_controller_state(
    provider: ProviderKind, device_id: str, state: Mapping, *, online=None,
) -> DeviceSnapshot:
    """Remote controller thing model (e.g. DeviceState_rc701, RC Plus 2)."""
    if provider not in (ProviderKind.PUBLIC_V2, ProviderKind.ONPREM_V2):
        raise DeviceStateError("FlightHub V2 provider required")
    _serial(device_id)
    if not isinstance(state, Mapping):
        raise DeviceStateError("Device state must be an object")
    latitude, longitude = _position(state)
    return parse_snapshot(provider, {
        "device_id": device_id,
        "online": _online(online),
        "latitude": latitude,
        "longitude": longitude,
        "battery_percent": state.get("capacity_percent"),
    })


def normalize_public_state(device_id: str, payload: Mapping) -> DeviceSnapshot:
    """Handle the DJI example's data.device_state (or direct data) response."""
    _serial(device_id)
    if not isinstance(payload, Mapping) or type(payload.get("code")) is not int or payload["code"] != 0:
        raise DeviceStateError("Unsuccessful DJI state response")
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise DeviceStateError("Missing DJI state data")
    for key in ("device_sn", "sn"):
        if key in data and data[key] != device_id:
            raise DeviceStateError("State belongs to a different aircraft")
    state = data.get("device_state", data)
    if not isinstance(state, Mapping):
        raise DeviceStateError("Invalid DJI state payload")
    return normalize_aircraft_state(
        ProviderKind.PUBLIC_V2, device_id, state,
        online_override=data.get("device_online_status"),
    )


def normalize_onprem_device(record: Mapping) -> DeviceSnapshot:
    """Only drone-class records are eligible; infrastructure is rejected."""
    if not isinstance(record, Mapping):
        raise DeviceStateError("Invalid On-Premises device")
    model = record.get("device_model")
    if not isinstance(model, Mapping) or model.get("class") != "drone":
        raise DeviceStateError("Not an aircraft device")
    device_id = _serial(record.get("device_sn"))
    state = record.get("device_state")
    if state is None:
        state = {}
    return normalize_aircraft_state(
        ProviderKind.ONPREM_V2, device_id, state,
        online_override=record.get("device_online_status"),
    )


def normalize_onprem_state_page(payload: Mapping) -> tuple[DeviceSnapshot, ...]:
    if not isinstance(payload, Mapping) or type(payload.get("code")) is not int or payload["code"] != 0:
        raise DeviceStateError("Unsuccessful DJI device list response")
    data = payload.get("data")
    items = data.get("list", ...) if isinstance(data, Mapping) else ...
    if items is None:
        items = []  # empty collections arrive as {"list": null}
    if not isinstance(items, list):
        raise DeviceStateError("Missing device list")
    seen = set()
    snapshots = []
    for item in items:
        if not isinstance(item, Mapping):
            raise DeviceStateError("Invalid device entry")
        model = item.get("device_model")
        if not isinstance(model, Mapping) or model.get("class") != "drone":
            continue
        snapshot = normalize_onprem_device(item)
        if snapshot.device_id in seen:
            raise DeviceStateError("Duplicate aircraft on page")
        seen.add(snapshot.device_id)
        snapshots.append(snapshot)
    return tuple(snapshots)


async def read_public_aircraft_state(
    config: ProviderConfig, project_uuid: str, device_id: str,
) -> DeviceSnapshot:
    if config.kind != ProviderKind.PUBLIC_V2:
        raise DeviceStateError("Public Cloud provider required")
    project_uuid = _uuid(project_uuid)
    device_id = _serial(device_id)
    path = f"/openapi/v2.0/device/{device_id}/state"
    client = ReadOnlyTransport(config, frozenset({path}))
    payload = await client.get(path, project_uuid=project_uuid)
    return normalize_public_state(device_id, payload)


async def read_onprem_aircraft_states(
    config: ProviderConfig, organization_uuid: str, *,
    page: int = 1, page_size: int = 20,
) -> tuple[DeviceSnapshot, ...]:
    """Read the existing On-Premises organization list; do not guess project IDs."""
    if config.kind != ProviderKind.ONPREM_V2:
        raise DeviceStateError("On-Premises provider required")
    organization_uuid = _uuid(organization_uuid)
    if type(page) is not int or type(page_size) is not int or not (1 <= page <= 100000 and 1 <= page_size <= 100):
        raise DeviceStateError("Invalid pagination")
    path = f"/openapi/v2.0/manage/api/v1/organizations/{organization_uuid}/manage-devices"
    client = ReadOnlyTransport(config, frozenset({path}))
    payload = await client.get(path, {
        "device_model_class": "drone",
        "page": page,
        "page_size": page_size,
    })
    return normalize_onprem_state_page(payload)


async def sync_public_aircraft_state(
    inventory: Inventory, config: ProviderConfig,
    project_uuid: str, device_id: str,
) -> DeviceSnapshot:
    """Update one registered aircraft's local snapshot; no DJI-side writes."""
    if not isinstance(inventory, Inventory):
        raise TypeError("Inventory required")
    if config.kind != ProviderKind.PUBLIC_V2:
        raise DeviceStateError("Public Cloud provider required")
    project_uuid = _uuid(project_uuid)
    device_id = _serial(device_id)
    device = inventory._devices.get((ProviderKind.PUBLIC_V2, project_uuid, device_id))
    if device is None or device.kind != DeviceType.AIRCRAFT:
        raise DeviceStateError("Registered aircraft required")
    snapshot = await read_public_aircraft_state(config, project_uuid, device_id)
    # The detail API may omit online status. Keep the last explicitly observed
    # value from the inventory instead of overwriting it with unknown.
    previous = inventory.telemetry(ProviderKind.PUBLIC_V2, project_uuid, device_id)
    if snapshot.online is None and previous is not None:
        snapshot = replace(snapshot, online=previous.online)
    register_snapshots(inventory, project_uuid, (snapshot,))
    return snapshot
