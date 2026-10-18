"""Bounded, read-only Pilot 2 map layers and device topology from the local Cloud API.

Uses the already verified local workspace session, never accepts arbitrary URLs,
never follows redirects and never emits storage URLs, user IDs or auth tokens.
No DJI HTTP write, MQTT publish, JSBridge or flight operation is performed.
"""
import asyncio
from datetime import datetime, timezone
from math import isfinite
import json
import re
import time
from uuid import UUID

import httpx

from .local_waylines import (ORIGIN, MAX_BODY, PAGE_SIZE, LocalWaylineError, credentials_path,
                             handoff_enabled, load_credentials)

CACHE_SECONDS = 20
MAX_GROUPS = 100
MAX_FEATURES = 500
MAX_DEVICES = 200
MAX_VERTICES = 5000
_MODEL = re.compile(r"[0-9]{1,5}-[0-9]{1,5}-[0-9]{1,5}\Z")
_SERIAL = re.compile(r"[A-Za-z0-9_:\-.]{1,100}\Z")


def _name(value, max_length=200):
    return value.strip() if isinstance(value, str) and 0 < len(value.strip()) <= max_length and all(
        ord(ch) >= 32 for ch in value) else None


def _uuid(value):
    try:
        return str(UUID(value)) if isinstance(value, str) else None
    except (ValueError, AttributeError):
        return None


def _point(value):
    if not isinstance(value, list) or len(value) not in (2, 3):
        return None
    if any(type(v) not in (float, int) or not isfinite(v) for v in value):
        return None
    lon, lat = value[:2]
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        return None
    if len(value) == 3 and not -10000 <= value[2] <= 100000:
        return None
    return value[:]


def _geometry(geometry):
    """Only DJI's documented WGS84 Point/LineString/Polygon subset is exported."""
    if not isinstance(geometry, dict):
        return None
    kind, coords = geometry.get("type"), geometry.get("coordinates")
    if kind == "Point":
        points = _point(coords)
    elif kind == "LineString":
        if not isinstance(coords, list) or not 2 <= len(coords) <= MAX_VERTICES:
            return None
        points = [_point(v) for v in coords]
        if any(v is None for v in points):
            return None
    elif kind == "Polygon":
        if not isinstance(coords, list) or not 1 <= len(coords) <= 50:
            return None
        points, count = [], 0
        for ring in coords:
            if not isinstance(ring, list) or not 4 <= len(ring) <= MAX_VERTICES:
                return None
            count += len(ring)
            if count > MAX_VERTICES:
                return None
            normalized = [_point(v) for v in ring]
            if any(v is None for v in normalized) or normalized[0][:2] != normalized[-1][:2]:
                return None
            points.append(normalized)
    else:
        return None
    if points is None:
        return None
    return {"type": kind, "coordinates": points}


def _map_payload(data):
    if not isinstance(data, list) or len(data) > MAX_GROUPS:
        raise LocalWaylineError("invalid_response")
    groups, features, skipped = [], [], 0
    for raw in data:
        if not isinstance(raw, dict) or not isinstance(raw.get("elements"), list):
            raise LocalWaylineError("invalid_response")
        identifier, name = _uuid(raw.get("id")), _name(raw.get("name"))
        if not identifier or name is None:
            raise LocalWaylineError("invalid_response")
        items = raw["elements"]
        if len(items) > MAX_FEATURES or len(features) + len(items) > MAX_FEATURES:
            raise LocalWaylineError("invalid_response")
        if type(raw.get("is_lock")) not in (bool, type(None)):
            raise LocalWaylineError("invalid_response")
        if type(raw.get("type")) not in (int, type(None)):
            raise LocalWaylineError("invalid_response")
        group = {"id": identifier, "name": name, "locked": raw.get("is_lock"),
                 "type_code": raw.get("type"), "source_elements": len(items),
                 "displayed_features": 0}
        groups.append(group)
        for item in items:
            if not isinstance(item, dict):
                raise LocalWaylineError("invalid_response")
            resource = item.get("resource")
            content = resource.get("content") if isinstance(resource, dict) else None
            geom = _geometry(content.get("geometry")) if isinstance(content, dict) and content.get("type") == "Feature" else None
            element_id, element_name = _uuid(item.get("id")), _name(item.get("name"))
            if not element_id or element_name is None or geom is None:
                skipped += 1
                continue
            features.append({"id": element_id, "group_id": identifier, "name": element_name,
                             "geometry": geom})
            group["displayed_features"] += 1
    return {"groups": groups, "features": features, "skipped_unsupported": skipped,
            "crs": "EPSG:4326", "complete": True}


def _model_component(value):
    """Normalize a bounded numeric DJI model component (bool is invalid)."""
    if type(value) is int:
        if not 0 <= value <= 99999:
            return None
        return str(value)
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,5}", value):
        return str(int(value))
    return None


def _device_model_key(model, role):
    """Decode either DJI device_model.key or numeric domain/type/sub_type.

    Reject malformed values, a wrong device domain, or conflicting fields.
    This is an identification label only, never a compatibility approval.
    """
    if not isinstance(model, dict):
        return None
    expected_domain = {"aircraft": "0", "controller": "2"}.get(role)
    if expected_domain is None:
        return None

    raw_key = model.get("key")
    if raw_key is not None:
        if not isinstance(raw_key, str) or not _MODEL.fullmatch(raw_key):
            return None
        key = "-".join(str(int(part)) for part in raw_key.split("-"))
    else:
        key = None

    field_names = ("domain", "type", "sub_type")
    present = [name in model for name in field_names]
    parts = [
        _model_component(model[name]) if name in model else None
        for name in field_names
    ]
    if any(is_present and part is None for is_present, part in zip(present, parts)):
        return None

    if key is not None:
        key_parts = key.split("-")
        if any(is_present and part != key_parts[i]
               for i, (is_present, part) in enumerate(zip(present, parts))):
            return None
        return key if key_parts[0] == expected_domain else None

    if not all(present) or parts[0] != expected_domain:
        return None
    return "-".join(parts)


def _device(value, role):
    if not isinstance(value, dict):
        return None
    serial = value.get("sn")
    model_key = _device_model_key(value.get("device_model"), role)
    if not isinstance(serial, str) or not _SERIAL.fullmatch(serial):
        return None
    status = value.get("online_status")
    if type(status) is not bool:
        status = None
    return {"serial_number": serial, "role": role, "device_model_key": model_key,
            "callsign": _name(value.get("device_callsign")), "online": status}


def _topology_payload(data):
    if not isinstance(data, dict) or not isinstance(data.get("list"), list) or len(data["list"]) > MAX_DEVICES:
        raise LocalWaylineError("invalid_response")
    nodes, links, seen = [], [], set()
    for row in data["list"]:
        if not isinstance(row, dict):
            raise LocalWaylineError("invalid_response")
        hosts, parents = row.get("hosts"), row.get("parents")
        if not isinstance(hosts, list) or not isinstance(parents, list):
            raise LocalWaylineError("invalid_response")
        if len(hosts) + len(parents) > MAX_DEVICES:
            raise LocalWaylineError("invalid_response")
        valid_hosts, valid_parents = [], []
        for values, role, result in ((hosts, "aircraft", valid_hosts), (parents, "controller", valid_parents)):
            for raw in values:
                device = _device(raw, role)
                if device is None:
                    continue
                key = (role, device["serial_number"])
                if key not in seen:
                    seen.add(key)
                    nodes.append(device)
                result.append(device["serial_number"])
        if len(nodes) > MAX_DEVICES:
            raise LocalWaylineError("invalid_response")
        for controller in valid_parents:
            for aircraft in valid_hosts:
                if len(links) >= MAX_DEVICES * 2:
                    raise LocalWaylineError("invalid_response")
                links.append({"controller_sn": controller, "aircraft_sn": aircraft})
    return {"devices": nodes, "links": links, "complete": True}


async def _local_get(credentials, path, *, transport=None):
    """Only constant paths with validated UUID workspace; HTTP response is not success."""
    async with httpx.AsyncClient(base_url=ORIGIN, timeout=5, trust_env=False,
                                 follow_redirects=False, transport=transport) as client:
        async with client.stream("GET", path, headers={"x-auth-token": credentials.access_token}) as response:
            if response.status_code in (401, 403):
                raise LocalWaylineError("authentication_required")
            if response.status_code != 200:
                raise LocalWaylineError("upstream_error")
            content = bytearray()
            async for chunk in response.aiter_bytes():
                if len(content) + len(chunk) > MAX_BODY:
                    raise LocalWaylineError("invalid_response")
                content.extend(chunk)
    try:
        value = json.loads(content)
    except (ValueError, UnicodeError, RecursionError):
        raise LocalWaylineError("invalid_response") from None
    if not isinstance(value, dict) or type(value.get("code")) is not int:
        raise LocalWaylineError("invalid_response")
    if value["code"] != 0:
        # Never expose the upstream 'message': it can contain private details.
        raise LocalWaylineError("business_error")
    return value.get("data")


async def read_map_elements(credentials, *, transport=None):
    data = await _local_get(credentials,
                            f"/map/api/v1/workspaces/{credentials.workspace_id}/element-groups",
                            transport=transport)
    return _map_payload(data)


async def read_device_topology(credentials, *, transport=None):
    data = await _local_get(credentials,
                            f"/manage/api/v1/workspaces/{credentials.workspace_id}/devices/topologies",
                            transport=transport)
    return _topology_payload(data)


async def _probe(credentials, path, *, params=None, transport=None):
    """One fixed-origin GET; expose HTTP/code only, never error messages or data."""
    async with httpx.AsyncClient(base_url=ORIGIN, timeout=5, trust_env=False,
                                 follow_redirects=False, transport=transport) as client:
        async with client.stream("GET", path, params=params,
                                 headers={"x-auth-token": credentials.access_token}) as response:
            status = response.status_code
            if status != 200:
                return {"http_status": status, "state": (
                    "authentication_required" if status in (401, 403) else "upstream_error")}
            content = bytearray()
            async for chunk in response.aiter_bytes():
                if len(content) + len(chunk) > MAX_BODY:
                    return {"http_status": status, "state": "invalid_response"}
                content.extend(chunk)
    try:
        value = json.loads(content)
    except (ValueError, UnicodeError, RecursionError):
        return {"http_status": status, "state": "invalid_response"}
    if not isinstance(value, dict) or type(value.get("code")) is not int:
        return {"http_status": status, "state": "invalid_response"}
    code = value["code"]
    return {"http_status": status, "api_code": code,
            "state": "ok" if code == 0 else "business_error"}


async def read_diagnostics(credentials, *, transport=None):
    """Probe ONLY documented safe GET endpoints; no STS, callback, upload or write."""
    workspace = credentials.workspace_id
    endpoints = {
        "session": ("/manage/api/v1/users/current", None),
        "waylines": (f"/wayline/api/v1/workspaces/{workspace}/waylines",
                     {"page": 1, "page_size": PAGE_SIZE, "order_by": "create_time asc"}),
        "map_elements": (f"/map/api/v1/workspaces/{workspace}/element-groups", None),
        "topology": (f"/manage/api/v1/workspaces/{workspace}/devices/topologies", None),
    }
    checks = {}
    for name, (path, params) in endpoints.items():
        try:
            checks[name] = await _probe(credentials, path, params=params, transport=transport)
        except (httpx.HTTPError, OSError, TimeoutError):
            checks[name] = {"state": "unavailable"}
    return {"checks": checks, "all_ok": all(v["state"] == "ok" for v in checks.values())}


class Pilot2ReadOnlyReader:
    """Independent 20s caches; an error clears last good data, no stale success."""
    def __init__(self):
        self._lock = asyncio.Lock()
        self._cached = {}

    async def _read(self, key, callback):
        async with self._lock:
            try:
                credentials = load_credentials(credentials_path())
            except LocalWaylineError:
                self._cached.clear()
                return {"state": "configuration_error"}
            if credentials is None:
                self._cached.clear()
                return {"state": "awaiting_browser_session" if handoff_enabled() else "not_configured"}
            cached = self._cached.get(key)
            if cached and cached[0] == credentials and time.monotonic() < cached[1]:
                return cached[2]
            try:
                result = await asyncio.wait_for(callback(credentials), timeout=12)
                result = {"state": "connected", "workspace_id": credentials.workspace_id,
                          "updated_at": datetime.now(timezone.utc).isoformat(), **result}
            except LocalWaylineError as exc:
                result = {"state": str(exc)}
            except (httpx.HTTPError, OSError, TimeoutError):
                result = {"state": "unavailable"}
            self._cached[key] = (credentials, time.monotonic() + CACHE_SECONDS, result)
            return result

    async def diagnostics(self):
        return await self._read("diagnostics", read_diagnostics)

    async def map_elements(self):
        return await self._read("map", read_map_elements)

    async def device_topology(self):
        return await self._read("topology", read_device_topology)
