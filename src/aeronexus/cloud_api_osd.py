"""DJI Cloud API OSD normalization (Pilot 2 -> MQTT broker), read-only.

Topic: thing/product/{device_sn}/osd. With DJI Pilot 2 the remote controller
(gateway) publishes its own OSD under its serial number and forwards the
aircraft OSD under the aircraft serial number.

The OSD payload carries no device model key, so the device type is derived
from documented property sets:
  aircraft  mode_code, elevation, position_state, battery {...}
  RC        capacity_percent / wireless_link without aircraft properties
Anything else is ignored rather than guessed. Device topology (the
sys/product/+/status update_topo message) is deliberately not read: it
carries device_secret and nonce.
"""
from collections.abc import Mapping
import json
from math import isfinite
import re

from .inventory import DeviceType


class CloudOsdError(ValueError):
    pass


OSD_TOPIC = "thing/product/+/osd"
MAX_PAYLOAD_BYTES = 65536
_TOPIC = re.compile(r"thing/product/([A-Za-z0-9_-]{1,80})/osd\Z")
_AIRCRAFT_KEYS = frozenset({"mode_code", "elevation", "position_state", "home_distance",
                            "horizontal_speed", "total_flight_sorties"})
_CONTROLLER_KEYS = frozenset({"capacity_percent", "wireless_link",
                              "transmission_signal_quality"})


def topic_serial(topic: str) -> str:
    match = _TOPIC.fullmatch(topic) if isinstance(topic, str) else None
    if match is None:
        raise CloudOsdError("Not a DJI OSD topic")
    return match.group(1)


def osd_data(payload: bytes) -> Mapping:
    """Bounded JSON decode of the Cloud API envelope; returns its data object."""
    if not isinstance(payload, (bytes, bytearray)) or not 0 < len(payload) <= MAX_PAYLOAD_BYTES:
        raise CloudOsdError("Invalid OSD payload size")
    try:
        message = json.loads(bytes(payload).decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise CloudOsdError("OSD payload is not JSON") from exc
    data = message.get("data") if isinstance(message, dict) else None
    if not isinstance(data, dict) or not data:
        raise CloudOsdError("OSD payload has no data object")
    return data


def classify(data: Mapping) -> DeviceType | None:
    keys = set(data)
    if keys & _AIRCRAFT_KEYS or isinstance(data.get("battery"), Mapping):
        return DeviceType.AIRCRAFT
    if keys & _CONTROLLER_KEYS:
        return DeviceType.CONTROLLER
    return None


def _number(value):
    """DJI sends numbers; some SDK samples type them as strings. Accept both."""
    if value is None or type(value) in (int, float):
        return value
    if isinstance(value, str) and 0 < len(value) <= 32:
        try:
            number = float(value)
        except ValueError:
            pass
        else:
            if isfinite(number):
                return int(number) if number.is_integer() and "." not in value else number
    raise CloudOsdError("Invalid numeric OSD value")


def _count(value):
    value = _number(value)
    if value is None or type(value) is int:
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise CloudOsdError("Invalid OSD count")


def _branch(data: Mapping, name: str) -> Mapping:
    value = data.get(name)
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise CloudOsdError(f"Invalid {name} structure")
    return value


def _put(fields: dict, source: Mapping, key: str, target: str, convert=_number) -> None:
    # Only properties present in this message are reported, so a partial OSD
    # push does not erase previously received values.
    if key in source:
        fields[target] = convert(source[key])


def normalize_osd(kind: DeviceType, data: Mapping) -> dict:
    """Map present OSD properties to canonical telemetry field names."""
    if not isinstance(data, Mapping):
        raise CloudOsdError("OSD data must be an object")
    fields: dict = {}
    if "latitude" in data or "longitude" in data:
        lat, lon = _number(data.get("latitude")), _number(data.get("longitude"))
        # DJI reports 0/0 when no position is known; that is not a location.
        if lat is None or lon is None or (lat == 0 and lon == 0):
            lat = lon = None
        fields["latitude"], fields["longitude"] = lat, lon
    if kind == DeviceType.CONTROLLER:
        _put(fields, data, "capacity_percent", "battery_percent")
        return fields
    _put(fields, data, "height", "height_m")
    _put(fields, data, "elevation", "elevation_m")
    _put(fields, data, "home_distance", "home_distance_m")
    _put(fields, data, "horizontal_speed", "horizontal_speed_mps")
    _put(fields, data, "vertical_speed", "vertical_speed_mps")
    _put(fields, data, "total_flight_time", "total_flight_time_s")
    _put(fields, data, "total_flight_sorties", "total_flight_sorties", _count)
    _put(fields, data, "mode_code", "flight_mode_code", _count)
    position = _branch(data, "position_state")
    _put(fields, position, "gps_number", "gps_satellites", _count)
    _put(fields, position, "rtk_number", "rtk_satellites", _count)
    if "is_fixed" in position:
        raw = _count(position["is_fixed"])
        # Raw DJI code, same labelling as the FlightHub reader; not a fix claim.
        fields["rtk_state"] = None if raw is None else f"is_fixed:{raw}"
    battery = _branch(data, "battery")
    _put(fields, battery, "capacity_percent", "battery_percent")
    packs = battery.get("batteries")
    if isinstance(packs, list) and packs and isinstance(packs[0], Mapping):
        _put(fields, packs[0], "voltage", "battery_voltage_mv")
        _put(fields, packs[0], "temperature", "battery_temperature_c")
    return fields
