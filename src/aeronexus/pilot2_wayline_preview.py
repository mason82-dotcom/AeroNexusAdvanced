"""Bounded, read-only DJI Pilot 2 KMZ geometry preview.

The DJI signed URL is validated but NEVER followed. Its path and query are
fetched exclusively from a fixed local MinIO socket, with the original signed
Host header preserved. No writes, flight commands or raw KMZ responses.
"""
import argparse
import asyncio
import json
from io import BytesIO
import ipaddress
import os
import re
from urllib.parse import unquote, urlsplit
from uuid import UUID
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

import httpx

from .local_waylines import (ORIGIN, Credentials, LocalWaylineError,
                             credentials_path, load_credentials, read_waylines)

MAX_KMZ = 4 * 1024 * 1024
MAX_MEMBER = 2 * 1024 * 1024
MAX_ELEMENTS = 1000
MAX_FEATURES = 32
MINIO_LOCAL = "http://127.0.0.1:9000"


def _tag(node):
    return node.tag.rsplit("}", 1)[-1] if isinstance(node.tag, str) else ""


def _coordinate(raw):
    try:
        nums = [float(v.strip()) for v in raw.split(",")]
    except (AttributeError, ValueError):
        raise LocalWaylineError("unsupported_geometry") from None
    if len(nums) not in (2, 3):
        raise LocalWaylineError("unsupported_geometry")
    from math import isfinite
    if (not all(isfinite(v) for v in nums)
            or not -180 <= nums[0] <= 180 or not -90 <= nums[1] <= 90):
        raise LocalWaylineError("unsupported_geometry")
    return nums[:2]


def _coord_text(node):
    for child in node.iter():
        if _tag(child) == "coordinates":
            return child.text
    return None


def _xml_root(data):
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise LocalWaylineError("invalid_archive")
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        raise LocalWaylineError("invalid_archive") from None
    if _tag(root) != "kml":
        raise LocalWaylineError("invalid_archive")
    return root


def _waypoint_features(data):
    root = _xml_root(data)
    features = []
    total = 0
    for folder in root.iter():
        if _tag(folder) != "Folder":
            continue
        points = []
        for item in folder:
            if _tag(item) != "Placemark":
                continue
            for element in item.iter():
                if _tag(element) == "Point":
                    points.append(_coordinate(_coord_text(element)))
                    total += 1
                    break
            if total > MAX_ELEMENTS:
                raise LocalWaylineError("invalid_archive")
        if points:
            if len(features) >= MAX_FEATURES:
                raise LocalWaylineError("invalid_archive")
            geom = ({"type": "LineString", "coordinates": points}
                    if len(points) >= 2 else
                    {"type": "Point", "coordinates": points[0]})
            features.append({"geometry": geom})
    return features, total


def _template_features(data):
    root = _xml_root(data)
    features = []
    total = 0
    for item in root.iter():
        kind = _tag(item)
        if kind not in ("Polygon", "LineString"):
            continue
        raw = _coord_text(item)
        if not raw:
            continue
        points = [_coordinate(v) for v in raw.split()]
        total += len(points)
        if total > MAX_ELEMENTS or len(features) >= MAX_FEATURES:
            raise LocalWaylineError("invalid_archive")
        if kind == "LineString" and len(points) >= 2:
            features.append({"geometry": {"type": kind, "coordinates": points}})
        if kind == "Polygon" and len(points) >= 4 and points[0] == points[-1]:
            features.append({"geometry": {"type": kind, "coordinates": [points]}})
    return features, total


def parse_preview_kmz(data: bytes) -> dict:
    """Extract only bounded coordinates from WPML, falling back to KML planning polygons."""
    if not data or len(data) > MAX_KMZ:
        raise LocalWaylineError("invalid_archive")
    try:
        with ZipFile(BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > 20 or len({i.filename for i in infos}) != len(infos):
                raise LocalWaylineError("invalid_archive")
            if any(i.flag_bits & 1 or i.file_size > MAX_MEMBER or
                   (i.external_attr >> 16) & 0o170000 == 0o120000 for i in infos):
                raise LocalWaylineError("invalid_archive")
            if sum(i.file_size for i in infos) > MAX_KMZ:
                raise LocalWaylineError("invalid_archive")
            selected = {info.filename: info for info in infos
                        if info.filename in {"wpmz/waylines.wpml", "wpmz/template.kml"}}
            def read_bounded(name):
                member = selected.get(name)
                if member is None:
                    return None
                # Never trust ZIP declared sizes alone; cap actual decompression.
                with archive.open(member) as reader:
                    body = reader.read(MAX_MEMBER + 1)
                if len(body) > MAX_MEMBER:
                    raise LocalWaylineError("invalid_archive")
                return body
            route = read_bounded("wpmz/waylines.wpml")
            template = read_bounded("wpmz/template.kml")
    except (BadZipFile, OSError, RuntimeError, EOFError):
        raise LocalWaylineError("invalid_archive") from None
    if route is not None:
        features, count = _waypoint_features(route)
        if features:
            return {"features": features, "point_count": count, "source": "waylines.wpml"}
    if template is not None:
        features, count = _template_features(template)
        if features:
            return {"features": features, "point_count": count, "source": "template.kml"}
    raise LocalWaylineError("unsupported_geometry")


def _signed_location(location):
    """Permit only private signed MinIO origins; actual socket is fixed loopback."""
    if not isinstance(location, str) or len(location) > 8192:
        raise LocalWaylineError("storage_origin_rejected")
    try:
        parts = urlsplit(location)
        port = parts.port
    except ValueError:
        raise LocalWaylineError("storage_origin_rejected") from None
    if (parts.scheme != "http" or port != 9000 or not parts.hostname
            or parts.username or parts.password or parts.fragment or not parts.query):
        raise LocalWaylineError("storage_origin_rejected")
    try:
        ip = ipaddress.ip_address(parts.hostname)
        if not (ip.is_private or ip.is_loopback):
            raise LocalWaylineError("storage_origin_rejected")
    except ValueError:
        if parts.hostname != "localhost":
            raise LocalWaylineError("storage_origin_rejected") from None
    bucket = os.getenv("AERONEXUS_MINIO_BUCKET", "dji-cloud")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket):
        raise LocalWaylineError("storage_origin_rejected")
    decoded = unquote(parts.path)
    if (not decoded.startswith("/" + bucket + "/") or
            any(segment in (".", "..") for segment in decoded.split("/"))
            or any(x in decoded for x in ("\x00", "\\", "\r", "\n"))):
        raise LocalWaylineError("storage_origin_rejected")
    return parts.netloc, parts.path + "?" + parts.query


async def _download_kmz(credentials: Credentials, wayline_id: str, *, transport=None) -> bytes:
    """A selected UUID and fixed loopback backend are required for both safe GETs."""
    try:
        wayline_id = str(UUID(wayline_id))
    except (TypeError, ValueError, AttributeError):
        raise LocalWaylineError("invalid_wayline_id") from None
    path = f"/wayline/api/v1/workspaces/{credentials.workspace_id}/waylines/{wayline_id}/url"
    async with httpx.AsyncClient(base_url=ORIGIN, timeout=8, trust_env=False,
                                 follow_redirects=False, transport=transport) as client:
        async with client.stream("GET", path,
                                 headers={"x-auth-token": credentials.access_token}) as response:
            if response.status_code in (401, 403):
                raise LocalWaylineError("authentication_required")
            if response.status_code != 302:
                raise LocalWaylineError("storage_unavailable")
            signed_host, signed_path = _signed_location(response.headers.get("location"))
    # The DJl token never reaches MinIO; the presigned URL never reaches the browser.
    async with httpx.AsyncClient(base_url=MINIO_LOCAL, timeout=12, trust_env=False,
                                 follow_redirects=False, transport=transport) as client:
        async with client.stream("GET", signed_path,
                                 headers={"Host": signed_host}) as response:
            if response.status_code != 200:
                raise LocalWaylineError("storage_unavailable")
            try:
                length = int(response.headers.get("content-length", "-1"))
            except ValueError:
                raise LocalWaylineError("invalid_archive") from None
            if length > MAX_KMZ:
                raise LocalWaylineError("invalid_archive")
            content = bytearray()
            async for chunk in response.aiter_bytes():
                if len(content) + len(chunk) > MAX_KMZ:
                    raise LocalWaylineError("invalid_archive")
                content.extend(chunk)
    return bytes(content)


async def read_preview(credentials: Credentials, wayline_id: str, *, transport=None) -> dict:
    """Expose only the bounded geometry subset to callers (never raw KMZ)."""
    content = await _download_kmz(credentials, wayline_id, transport=transport)
    return parse_preview_kmz(content)



async def diagnose_previews(limit: int = 1, *, preview_reader=None, inventory_reader=None) -> dict:
    """Opt-in local CLI probe: index/status only, never names, UUIDs or signed URLs."""
    if type(limit) is not int or not 1 <= limit <= 8:
        raise ValueError("limit must be between 1 and 8")
    try:
        credentials = load_credentials(credentials_path())
    except LocalWaylineError:
        return {"inventory_state": "configuration_error", "results": []}
    if credentials is None:
        return {"inventory_state": "not_configured", "results": []}
    read_inventory = inventory_reader or read_waylines
    read_one = preview_reader or read_preview
    try:
        inventory = await asyncio.wait_for(read_inventory(credentials), timeout=15)
    except LocalWaylineError as exc:
        return {"inventory_state": str(exc), "results": []}
    except (httpx.HTTPError, OSError, TimeoutError):
        return {"inventory_state": "unavailable", "results": []}
    if not inventory.get("pagination_complete"):
        return {"inventory_state": "incomplete_inventory", "results": []}
    selected = inventory["waylines"][:limit]
    checks = []
    for index, route in enumerate(selected, start=1):
        try:
            geometry = await asyncio.wait_for(
                read_one(credentials, route["wayline_id"]), timeout=22)
            checks.append({"index": index, "state": "connected",
                           "feature_count": len(geometry["features"]),
                           "point_count": geometry["point_count"],
                           "source": geometry["source"]})
        except LocalWaylineError as exc:
            checks.append({"index": index, "state": str(exc)})
        except (httpx.HTTPError, OSError, TimeoutError):
            checks.append({"index": index, "state": "unavailable"})
    return {"inventory_state": "connected", "reported_total": inventory["reported_total"],
            "pagination_complete": True, "results": checks}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lesender KMZ-Vorschautest für bis zu acht inventarisierte Pilot-2-Waylines. "
                    "Keine IDs, Namen, Tokens oder signierten URLs in der Ausgabe.")
    parser.add_argument("--limit", type=int, choices=range(1, 9), default=1,
                        metavar="1..8", help="Anzahl zu prüfender Cloud-Waylines (Standard: 1)")
    args = parser.parse_args()
    result = asyncio.run(diagnose_previews(args.limit))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["inventory_state"] == "connected" and all(
        entry["state"] == "connected" for entry in result["results"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
