"""Optional read-only Cloud API 2 bridge for DJI's official Java SDK skeleton BFF.

Reference (dji-sdk/Cloud-API-2, devkit/skeleton):
  GET /api/v1/devices -> List<DeviceState>
  DeviceState(sn, deviceType, model, name, online, lastOsd, lastOsdAt,
              recentHms, onlineSince, childDevices)
  OsdData(attributes: Map<String,Object>)

DJI Cloud API 2's native SDK is x86_64/amd64 and cannot be imported into
the Python/ARM64 Raspberry Pi application. Only an ALREADY-RUNNING,
separately authenticated BFF on a trusted private server may be queried.
NEVER attempt direct DJI device access, SDK control, login, or any POST.
"""
import asyncio
from copy import deepcopy
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
import ipaddress
import os
import re
import time
from urllib.parse import urlsplit

import httpx


_DEVICE_PATH = "/api/v1/devices"
_SERIAL = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
_ALLOWED_NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9.-]{0,252}\Z")
MAX_DEVICES = 50
MAX_RESPONSE_BYTES = 1_000_000
MAX_HMS = 8
CACHE_SECONDS = 15


class CloudApi2BridgeError(ValueError):
    pass


@dataclass(frozen=True, repr=False)
class CloudApi2Settings:
    base_url: str
    api_token: str
    stale_after_seconds: int = 45

    def __post_init__(self):
        url = urlsplit(self.base_url)
        host = url.hostname
        if (not host or url.path not in ("", "/") or url.query or url.fragment
                or url.username or url.password or url.port is not None and not 1 <= url.port <= 65535):
            raise CloudApi2BridgeError("Cloud API 2 URL must be an origin without credentials")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if not _ALLOWED_NAME.fullmatch(host) or not host.lower().endswith((".lan", ".local")):
                raise CloudApi2BridgeError("Cloud API 2 server must be on a private LAN")
            is_loopback = False
        else:
            if not address.is_private and not address.is_loopback:
                raise CloudApi2BridgeError("Cloud API 2 server must use a private IP")
            is_loopback = address.is_loopback
        if url.scheme != "https" and not (url.scheme == "http" and is_loopback):
            raise CloudApi2BridgeError("HTTPS required (except direct loopback)")
        if not isinstance(self.api_token, str) or not 16 <= len(self.api_token) <= 8192 or any(
                ord(ch) < 33 or ord(ch) > 126 for ch in self.api_token):
            raise CloudApi2BridgeError("Backend API token is missing or invalid")
        if type(self.stale_after_seconds) is not int or not 5 <= self.stale_after_seconds <= 3600:
            raise CloudApi2BridgeError("Invalid telemetry staleness threshold")

    @classmethod
    def from_env(cls, environ=None) -> "CloudApi2Settings | None":
        env = os.environ if environ is None else environ
        if env.get("AERONEXUS_CLOUDAPI2_ENABLED") != "1":
            return None
        return cls(
            base_url=env.get("AERONEXUS_CLOUDAPI2_BFF_URL", ""),
            api_token=env.get("AERONEXUS_CLOUDAPI2_BFF_TOKEN", ""),
            stale_after_seconds=int(env.get("AERONEXUS_CLOUDAPI2_STALE_SECONDS", "45")),
        )

    def __repr__(self):
        return (f"CloudApi2Settings(base_url={self.base_url!r}, "
                f"api_token='<redacted>', stale_after_seconds={self.stale_after_seconds})")


def _text(value, limit=120) -> str | None:
    return value.strip()[:limit] if isinstance(value, str) and value.strip() else None


def _number(value, low=None, high=None):
    if type(value) not in (int, float):
        return None
    value = float(value)
    if value != value or abs(value) == float("inf"):
        return None
    if low is not None and value < low or high is not None and value > high:
        return None
    return value


def _date(value: str | None) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _normalize_hms(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    result = []
    for alert in value[:MAX_HMS]:
        if not isinstance(alert, dict):
            continue
        level = str(alert.get("level", "")).lower()
        level = ("warning" if level in ("warning", "critical", "error") else
                 "reminder" if level in ("reminder", "notice") else "notification")
        code = _text(alert.get("alertCode"), 32)
        if not code:
            continue
        result.append({
            "code": code, "level": level, "message": _text(alert.get("message"), 250),
            "timestamp": _text(alert.get("timestamp"), 40),
        })
    return result


def normalize_devices(payload, *, now: datetime | None = None,
                      stale_after_seconds: int = 45) -> list[dict]:
    """Flatten only DRONE records; skip DOCK and every other device type."""
    if not isinstance(payload, list):
        raise CloudApi2BridgeError("Unexpected Cloud API 2 response format")
    current = now or datetime.now(timezone.utc)
    rows, seen = [], set()

    def visit(device, depth=0):
        if depth > 3 or not isinstance(device, dict):
            raise CloudApi2BridgeError("Invalid Cloud API 2 device topology")
        kind = device.get("deviceType")
        if kind == "DRONE":
            serial = device.get("sn")
            if not isinstance(serial, str) or not _SERIAL.fullmatch(serial):
                raise CloudApi2BridgeError("Invalid Cloud API 2 device ID")
            if serial in seen:
                return  # SDK exposes some devices as flat rows and nested children
            if len(rows) >= MAX_DEVICES:
                raise CloudApi2BridgeError("Cloud API 2 device limit exceeded")
            seen.add(serial)
            raw = device.get("lastOsd")
            if raw is None:
                attrs = {}
            elif isinstance(raw, dict) and isinstance(raw.get("attributes"), dict):
                attrs = raw["attributes"]
            else:
                raise CloudApi2BridgeError("Unexpected Cloud API 2 OSD structure")
            latitude = _number(attrs.get("latitude"), -90, 90)
            longitude = _number(attrs.get("longitude"), -180, 180)
            if latitude is None or longitude is None or latitude == 0 and longitude == 0:
                latitude = longitude = None
            received = _date(device.get("lastOsdAt"))
            age = (current - received).total_seconds() if received else None
            freshness = ("missing" if received is None or raw is None else
                         "clock_skew" if age is not None and age < -1 else
                         "fresh" if age is not None and age <= stale_after_seconds else "stale")
            online = device.get("online") is True
            rows.append({
                "provider": "dji-cloud-api-2", "project_id": "cloud-api-2",
                "kind": "aircraft",
                "device_id": serial,
                "name": _text(device.get("name")) or _text(device.get("model")) or "DJI-Fluggerät",
                "model": _text(device.get("model")),
                "online": online if freshness == "fresh" else None,
                "reported_online": online,
                "freshness": freshness,
                "age_seconds": round(max(age, 0), 2) if age is not None and age >= 0 else None,
                "received_at": received.isoformat().replace("+00:00", "Z") if received else None,
                "telemetry": {
                    "battery_percent": _number(attrs.get("battery_percent"), 0, 100),
                    "latitude": latitude, "longitude": longitude,
                    "height_m": _number(attrs.get("altitude"), -500, 12000),
                    "speed_mps": _number(attrs.get("speed"), 0, 120),
                    # OSD 'mode' is a source string and must not be guessed to be a
                    # DJI Cloud API numeric flight_mode_code enum.
                    "flight_mode_label": _text(attrs.get("mode"), 50),
                },
                "health": _normalize_hms(device.get("recentHms")),
            })
        children = device.get("childDevices") or []
        if not isinstance(children, list) or len(children) > MAX_DEVICES:
            raise CloudApi2BridgeError("Invalid Cloud API 2 child device list")
        for child in children:
            visit(child, depth + 1)

    for item in payload[:MAX_DEVICES + 1]:
        visit(item)
    if len(payload) > MAX_DEVICES:
        raise CloudApi2BridgeError("Cloud API 2 device limit exceeded")
    return rows


@dataclass
class CloudApi2Bridge:
    settings: CloudApi2Settings
    _cached: list[dict] = field(default_factory=list)
    _updated_at: float = 0.0
    _status: str = "waiting"
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    async def read(self) -> dict:
        # A single BFF GET for all browsers, capped at 1 request / 15 seconds.
        async with self._lock:
            now = time.monotonic()
            if self._updated_at and now - self._updated_at < CACHE_SECONDS:
                return self._response()
            self._updated_at = now
            try:
                async with httpx.AsyncClient(
                    base_url=self.settings.base_url, timeout=7,
                    follow_redirects=False, trust_env=False, verify=True,
                ) as client:
                    async with client.stream("GET", _DEVICE_PATH, headers={
                        "Authorization": "Bearer " + self.settings.api_token,
                        "Accept": "application/json",
                        "User-Agent": "AeroNexusAdvanced/0.1 CloudAPI2 read-only",
                    }) as response:
                        if response.status_code != 200:
                            raise CloudApi2BridgeError("Cloud API 2 backend unavailable")
                        content = bytearray()
                        async for chunk in response.aiter_bytes(chunk_size=65536):
                            if len(content) + len(chunk) > MAX_RESPONSE_BYTES:
                                raise CloudApi2BridgeError("Cloud API 2 response too large")
                            content.extend(chunk)
                    devices = normalize_devices(
                        json.loads(content),
                        stale_after_seconds=self.settings.stale_after_seconds,
                    )
                self._cached = devices
                self._status = "ok"
            except (httpx.HTTPError, ValueError, UnicodeDecodeError):
                # Never leak JWT, upstream URL, response body, or stack traces.
                self._cached = []
                self._status = "unavailable"
            return self._response()

    def _response(self) -> dict:
        devices = deepcopy(self._cached)
        now = datetime.now(timezone.utc)
        for device in devices:
            received = _date(device["received_at"])
            age = (now - received).total_seconds() if received else None
            # Missing OSD remains missing even when lastOsdAt exists.
            if device["freshness"] != "missing":
                device["freshness"] = (
                    "clock_skew" if age is not None and age < -1 else
                    "fresh" if age is not None and age <= self.settings.stale_after_seconds
                    else "stale")
            device["age_seconds"] = round(max(age, 0), 2) if age is not None and age >= 0 else None
            device["online"] = device["reported_online"] if device["freshness"] == "fresh" else None
        return {"state": self._status, "source": "dji-cloud-api-2",
                "devices": devices, "total": len(devices)}
