"""DJI Cloud API HMS warning decoding from DJI's multilingual hms.json.

No network calls. Full upstream code catalog is operator-installed separately:
https://developer.dji.com/doc/cloud-api-tutorial/en/feature-set/dock-feature-set/hms.html

Key rules: dock_tip_{code}, fpv_tip_{code}[_in_the_sky].
HMS level is part of the telemetry, never inferred from diagnostic wording.
"""
from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
import json
import os
from pathlib import Path
import re

LEVELS = ("notification", "reminder", "warning")
MODULES = ("Flugmission", "Geräteverwaltung", "Medien", "HMS")
CODE = re.compile(r"(?:0x)?[0-9a-fA-F]{8}\Z")
KEY = re.compile(r"(?:dock|fpv)_tip_0x[0-9a-fA-F]{8}(?:_in_the_sky)?\Z")
PLACEHOLDER = re.compile(
    r"%(?:alarmid|component_index|sensor_index|index|battery_index|"
    r"dock_cover_index|charging_rod_index|(?:\d+\$)?s)"
)
CATALOG_MAX_BYTES = 6 * 1024 * 1024
MAX_ENTRIES = 10000

# Small, verifiable offline fallbacks; full coverage requires DJI's hms.json.
FALLBACK = {
    "dock_tip_0x12040000": {"de": "RTK-Gerät getrennt", "en": "RTK device disconnected"},
    "dock_tip_0x12040002": {"de": "Fehler des RTK-Geräts", "en": "RTK device error"},
    "dock_tip_0x12040004": {"de": "Fehler bei der Initialisierung des RTK-Geräts",
                             "en": "RTK device initialization error"},
    "dock_tip_0x17000004": {"en": "Image transmission signal weak"},
    "dock_tip_0x17000005": {"de": "Starke Signalstörungen am Gerät. Vorsichtig fliegen",
                             "en": "Strong signal interference. Fly with caution"},
}


def catalog_path() -> Path:
    return Path(os.environ.get("AERONEXUS_HMS_CATALOG_PATH") or
                Path.home() / ".config" / "aeronexusadvanced" / "hms.json")


def normalize_code(value) -> str | None:
    if isinstance(value, str) and CODE.fullmatch(value.strip()):
        return "0x" + value.strip().removeprefix("0x").removeprefix("0X").upper().zfill(8)
    return None


def _clean(value, maximum=400) -> str | None:
    if not isinstance(value, str):
        return None
    result = "".join(c if c.isprintable() else " " for c in value).strip()
    return result[:maximum] if result else None


@lru_cache(maxsize=4)
def _read_catalog(path: str, mtime_ns: int, size: int) -> Mapping:
    try:
        with Path(path).open("rb") as file:
            raw = file.read(CATALOG_MAX_BYTES + 1)
        if len(raw) > CATALOG_MAX_BYTES:
            return {}
        entries = json.loads(raw)
        if not isinstance(entries, dict) or len(entries) > MAX_ENTRIES:
            return {}
        # Never expose unknown fields or unvalidated copy keys.
        return {
            key.lower(): {lang: _clean(entry.get(lang)) for lang in ("de", "en")}
            for key, entry in entries.items()
            if isinstance(key, str) and KEY.fullmatch(key)
            and isinstance(entry, dict)
        }
    except (OSError, UnicodeError, ValueError):
        return {}


def catalog() -> Mapping:
    path = catalog_path()
    try:
        if path.is_symlink() or not path.is_file():
            return FALLBACK
        stat = path.stat()
        if stat.st_size > CATALOG_MAX_BYTES or stat.st_size < 2:
            return FALLBACK
        return {**FALLBACK, **_read_catalog(str(path), stat.st_mtime_ns, stat.st_size)}
    except OSError:
        return FALLBACK


def _indexed(value, *, offset=0) -> int | None:
    if type(value) is int and 0 <= value <= 32:
        return value + offset
    if isinstance(value, str) and value.isdecimal() and len(value) <= 2:
        n = int(value)
        if n <= 32:
            return n + offset
    return None


def _render(template: str, code: str, args: Mapping, *, dock: bool) -> str:
    sensor = _indexed(args.get("sensor_index"))
    component = _indexed(args.get("component_index"), offset=1)
    charging = ("vorn", "hinten", "links", "rechts")

    def variable(match):
        marker = match.group()
        if marker == "%alarmid":
            return code
        if marker in ("%index", "%sensor_index"):
            return str(sensor + 1) if sensor is not None else "?"
        if marker == "%component_index":
            return str(component) if component is not None else "?"
        if marker in ("%battery_index", "%dock_cover_index"):
            return ("links" if sensor == 0 else "rechts") if sensor is not None else "?"
        if marker == "%charging_rod_index":
            return charging[sensor] if sensor is not None and sensor < 4 else "?"
        if marker in ("%s", "%1$s", "%2$s"):
            if dock and sensor is not None:
                return "links" if sensor == 0 else "rechts"
            return str(component) if component is not None else "?"
        return "?"
    return _clean(PLACEHOLDER.sub(variable, template), 400) or "HMS-Meldung"


def severity(value) -> str:
    if type(value) is int and 0 <= value <= 2:
        return LEVELS[value]
    if isinstance(value, str):
        lower = value.strip().lower()
        if lower in LEVELS:
            return lower
        if lower in ("0", "1", "2"):
            return LEVELS[int(lower)]
    return "unknown"


def _flag(value) -> bool:
    return value is True or value == 1 or value == "1" or value == "in_the_sky"


def _kind_for_message(item: Mapping, kind: str) -> str:
    """DJI reports device domain in device_type: drone=0, dock=3.

    A gateway's HMS list may contain both dock and drone alerts.
    Never infer the alarm owner from the MQTT topic's device type.
    """
    device_type = item.get("device_type")
    if isinstance(device_type, str):
        match = re.fullmatch(r"([0-3])-[0-9]{1,4}-[0-9]{1,4}", device_type)
        if match:
            return {"0": "aircraft", "1": "aircraft",
                    "2": "controller", "3": "dock"}[match.group(1)]
    return kind


def _module(value) -> str | None:
    if type(value) is int and 0 <= value < len(MODULES):
        return MODULES[value]
    if isinstance(value, str) and value.isdecimal() and int(value) < len(MODULES):
        return MODULES[int(value)]
    return None


def resolve_hms(item: Mapping, *, kind: str = "aircraft") -> dict | None:
    """Normalize one FlightHub or Cloud API alarm with no guessed code descriptions."""
    if not isinstance(item, Mapping):
        return None
    code = normalize_code(item.get("code"))
    if code is None:
        # FlightHub may contain non-hex proprietary HMS codes; show raw code
        # without claiming a Cloud API diagnostic.
        code = _clean(item.get("code"), 64)
    if not code:
        return None
    in_sky = _flag(item.get("in_the_sky"))
    imminent = _flag(item.get("imminent"))
    args = item.get("args") if isinstance(item.get("args"), Mapping) else {}
    device_type = _clean(item.get("device_type"), 32)
    resolved_kind = _kind_for_message(item, kind)
    explicit_dock = resolved_kind == "dock"
    keys = []
    if normalize_code(code):
        if explicit_dock:
            keys = ["dock_tip_" + code]
        elif resolved_kind == "aircraft":
            if in_sky:
                keys.append("fpv_tip_" + code + "_in_the_sky")
            keys.append("fpv_tip_" + code)
        else:
            # Don't guess whether a gateway-originated alarm concerns the dock
            # or aircraft if no trusted device-kind context is available.
            keys = []
    entries = catalog()
    found = next(((key, entries[key.lower()]) for key in keys if key.lower() in entries), None)
    message = _clean(item.get("message"))
    source = "upstream" if message else "unknown"
    if found:
        key, translated = found
        text = translated.get("de") or translated.get("en")
        if text:
            message = _render(text, code, args, dock=explicit_dock)
            source = "dji-hms-catalog-de" if translated.get("de") else "dji-hms-catalog-en"
    return {
        "code": code, "level": severity(item.get("level")),
        "module": _module(item.get("module")), "message": message,
        "message_source": source,
        "imminent": imminent, "in_the_sky": in_sky,
        "device_type": device_type,
        "device_domain": resolved_kind,
        "source": "dji-cloud-hms",
    }


def normalize_cloud_hms_event(
    payload: bytes, *, kind: str = "aircraft"
) -> tuple[tuple[dict, ...], int | None]:
    """Validated full-snapshot HMS MQTT event; empty list means alarms resolved."""
    if not isinstance(payload, (bytes, bytearray)) or not 0 < len(payload) <= 65536:
        raise ValueError("Invalid HMS event size")
    try:
        obj = json.loads(payload)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Invalid HMS JSON event") from exc
    if not isinstance(obj, dict) or obj.get("method", "hms") != "hms":
        raise ValueError("Not an HMS event")
    # DJI's published HMS JSON example omits the method field; its
    # MQTT message envelope usually supplies it. Missing method is only
    # accepted with strict HMS-specific item structure below.
    data = obj.get("data")
    rows = data.get("list") if isinstance(data, dict) else None
    if not isinstance(rows, list) or len(rows) > 20:
        raise ValueError("Invalid HMS event list")
    timestamp = obj.get("timestamp")
    if timestamp is not None and (
            type(timestamp) is not int or timestamp < 0 or timestamp > 253402300799999):
        raise ValueError("Invalid HMS timestamp")
    if obj.get("method") is None and not rows:
        # Methodless empty events could be unrelated to HMS.
        raise ValueError("Methodless empty event cannot clear alarms")
    if any(not isinstance(row, dict) or normalize_code(row.get("code")) is None
           or type(row.get("level")) is not int or row["level"] not in (0, 1, 2)
           or type(row.get("module")) is not int or row["module"] not in (0, 1, 2, 3)
           for row in rows):
        raise ValueError("Invalid HMS item")
    # No free-form text, device SN or arbitrary properties are preserved.
    alerts = tuple(resolve_hms(row, kind=kind) for row in rows)
    return tuple(a for a in alerts if a), timestamp
