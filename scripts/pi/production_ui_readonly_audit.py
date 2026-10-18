#!/usr/bin/env python3
"""Verified HTTPS, GET-only, privacy-preserving live AeroNexus UI/API acceptance.

Run from a separate worktree using --instance-dir to point to the DEPLOYED
service's existing .env and CA. Never writes, posts, restarts, follows redirects,
logs serial numbers/positions, or persists response bodies. Does NOT constitute
an exhaustive live-browser or DJI flight certification.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import ipaddress
import json
from pathlib import Path
import re
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener
)

from dotenv import dotenv_values


# Only literal, reviewed GET endpoints. No caller-derived URL is accepted.
HTML_CHECKS = (
    ("/health", "health"),
    ("/studio", "studio"),
    ("/status", "status"),
    ("/operations", "operations"),
    ("/media", "media"),
    ("/thermal", "thermal"),
    ("/multispectral", "multispectral"),
    ("/results", "results"),
)
API_CHECKS = (
    ("/api/v1/status/summary", "status_summary", True),
    ("/api/v1/status/devices?limit=5", "status_devices", True),
    ("/api/v1/studio/missions", "studio_missions", True),
    ("/api/v1/studio/media", "studio_media", True),
    ("/api/v1/studio/geo-objects", "studio_geo", True),
    ("/api/v1/cloud/stack", "cloud_stack", False),
    ("/api/v1/flighthub/catalog", "flighthub_catalog", False),
    ("/api/v1/cloudapi2/devices", "cloudapi2", False),
    ("/api/v1/studio/dji-media?limit=10", "dji_media", False),
    ("/api/v1/dji/media/summary", "dji_summary", False),
    ("/api/v1/dji/media?limit=5", "dji_catalog", False),
    ("/api/v1/media/sync", "media_sync", False),
    ("/api/v1/photos/summary", "photo_summary", False),
    ("/api/v1/photos?limit=5", "photo_list", False),
    ("/api/v1/photos/map", "photo_map", False),
    ("/api/v1/thermal/status", "thermal_status", False),
    ("/api/v1/thermal/images?limit=5", "thermal_images", False),
    ("/api/v1/thermal/flights", "thermal_flights", False),
    ("/api/v1/multispectral/captures", "multispectral_captures", False),
    ("/api/v1/multispectral/map", "multispectral_map", False),
    ("/api/v1/multispectral/metashape/packages", "metashape_packages", False),
    ("/api/v1/results?limit=5", "raster_results", False),
    ("/api/v1/live/streams", "live_streams", False),
)
FIELDS = {
    "status_summary": ("registered_devices",),
    "status_devices": ("total", "devices"),
    "studio_missions": ("missions",),
    "studio_media": ("media",),
    "studio_geo": ("objects",),
    "cloud_stack": ("overall", "services", "fleet"),
    "flighthub_catalog": ("projects",),
    "cloudapi2": ("state", "devices"),
    "dji_media": ("media", "total"),
    "dji_summary": ("state",),
    "dji_catalog": ("items", "total"),
    "media_sync": (),
    "photo_summary": (),
    "photo_list": (),
    "photo_map": (),
    "thermal_status": ("sdk", "thermal_images"),
    "thermal_images": (),
    "thermal_flights": ("flights",),
    "multispectral_captures": ("captures", "total"),
    "multispectral_map": ("items",),
    "metashape_packages": ("packages",),
    "raster_results": ("items", "total"),
    "live_streams": ("available", "streams"),
}
# If a response grows too large, report SKIP (bounded), never print content.
MAX_HTML = 1_500_000
MAX_JSON = 1_000_000
MAX_PREVIEW_BYTES = 24


class RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError("redirect rejected")


@dataclass(frozen=True)
class AuditResult:
    label: str
    state: str
    reason: str


class ReadOnlyClient:
    def __init__(self, *, host: str, port: int, cafile: Path, token: str = "",
                 timeout: int = 8):
        addr = ipaddress.IPv4Address(host)
        if not addr.is_private or addr.is_multicast or addr.is_unspecified:
            raise ValueError("Private IPv4 LAN host required")
        if not 1 <= port <= 65535:
            raise ValueError("Invalid port")
        if not cafile.is_file():
            raise ValueError("Local CA certificate missing")
        context = ssl.create_default_context(cafile=str(cafile))
        self._opener = build_opener(
            ProxyHandler({}), HTTPSHandler(context=context), RejectRedirect()
        )
        self.base = f"https://{addr}:{port}"
        self.timeout = timeout
        self.headers = {"Cache-Control": "no-store", "Accept": "application/json, text/html"}
        if token:
            if not 32 <= len(token) <= 512 or not token.isascii() or any(c.isspace() for c in token):
                raise ValueError("Invalid dashboard access token")
            self.headers["Authorization"] = "Bearer " + token

    def read(self, path: str, *, max_bytes: int = MAX_JSON) -> tuple[int, str, bytes, bool]:
        if path not in {x[0] for x in HTML_CHECKS} | {x[0] for x in API_CHECKS}:
            raise ValueError("Unreviewed read path")
        return self._read_reviewed(path, max_bytes)

    def _read_reviewed(self, path: str, max_bytes: int, *, partial: bool = False) -> tuple[int, str, bytes, bool]:
        # All calls use this single audited GET-only transport.
        request = Request(self.base + path, headers=self.headers, method="GET")
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                size = response.headers.get("Content-Length")
                if not partial and size and size.isdigit() and int(size) > max_bytes:
                    return response.status, response.headers.get("Content-Type", ""), b"", True
                body = response.read(max_bytes + 1)
                return (response.status, response.headers.get("Content-Type", ""),
                        body[:max_bytes], len(body) > max_bytes)
        except HTTPError as exc:
            return exc.code, "", b"", False

    def preview(self, media_id: str) -> tuple[int, str, bytes, bool]:
        if not re.fullmatch(r"[0-9a-f]{64}", media_id):
            raise ValueError("Invalid opaque media id")
        # Explicit opt-in only; GET of a small, already-indexed browser-safe
        # object. This is a binary signature check, NOT image rendering.
        return self._read_reviewed(
            f"/api/v1/studio/dji-media/{media_id}/file", MAX_PREVIEW_BYTES, partial=True
        )


def configured_client(instance_dir: Path) -> ReadOnlyClient:
    env_path = instance_dir / ".env"
    if not env_path.is_file():
        raise ValueError("Missing production .env")
    env = dotenv_values(env_path)
    host = (env.get("AERONEXUS_LAN_HOST") or
            env.get("AERONEXUS_BIND") or "").strip()
    port = int(env.get("AERONEXUS_PORT") or "8000")
    if not host:
        raise ValueError("Missing AERONEXUS_LAN_HOST/BIND")
    token = "" if env.get("AERONEXUS_LAN_NO_TOKEN") == "1" else (
        env.get("AERONEXUS_STATUS_TOKEN") or ""
    )
    if env.get("AERONEXUS_LAN_NO_TOKEN") != "1" and not token:
        raise ValueError("Viewer token missing (no LAN-no-token setting)")
    ca = instance_dir / "config" / "pki" / "ca.crt"
    return ReadOnlyClient(host=host, port=port, cafile=ca, token=token)


def classify_html(label: str, status: int, mime: str, content: bytes,
                  too_large: bool) -> AuditResult:
    if status != 200:
        return AuditResult(label, "FAIL", "HTTP " + str(status))
    if too_large:
        return AuditResult(label, "SKIP", "HTML exceeds audit byte limit")
    if label == "health":
        try:
            valid = json.loads(content).get("status") == "ok"
        except (ValueError, AttributeError):
            valid = False
    else:
        expected = {
            "studio": b'id="point-action-add"',
            "status": b'id="devices"',
            "operations": b'id="refresh-now"',
            "media": b'id="media-rows"',
            "thermal": b'id="tab-flights"',
            "multispectral": b'id="layer"',
            "results": b'id="controls"',
        }
        valid = ("text/html" in mime.lower() and
                 len(content) >= 200 and expected[label] in content)
    return AuditResult(label, "PASS" if valid else "FAIL",
                       "verified HTTPS HTML" if valid else "unexpected HTML/health")


def classify_api(label: str, status: int, mime: str, body: bytes,
                 too_large: bool, *, optional: bool) -> tuple[AuditResult, dict[str, Any] | None]:
    if optional and status in (404, 501, 503):
        return AuditResult(label, "SKIP", "optional source unavailable (HTTP " + str(status) + ")"), None
    if status != 200:
        return AuditResult(label, "FAIL", "HTTP " + str(status)), None
    if too_large:
        return AuditResult(label, "SKIP", "bounded response size"), None
    try:
        if "application/json" not in mime.lower():
            raise ValueError("unexpected content type")
        value = json.loads(body)
        if not isinstance(value, dict):
            raise ValueError("not a JSON object")
        missing = [key for key in FIELDS[label] if key not in value]
        if missing:
            raise ValueError("missing expected schema fields")
    except (ValueError, UnicodeError):
        return AuditResult(label, "FAIL", "invalid JSON/schema"), None
    return AuditResult(label, "PASS", "live GET / schema valid"), value


def choose_preview(data: dict[str, Any] | None) -> str | None:
    if not isinstance(data, dict):
        return None
    for item in data.get("media", [])[:10]:
        if not isinstance(item, dict):
            continue
        media_id = item.get("id")
        mime = item.get("mime")
        size = item.get("size_bytes")
        if (isinstance(media_id, str) and re.fullmatch(r"[0-9a-f]{64}", media_id)
                and mime in ("image/jpeg", "image/png", "image/webp")
                and isinstance(size, int) and 0 < size <= 512 * 1024
                and item.get("previewable") is True):
            return media_id
    return None


def check_preview(client: ReadOnlyClient, listing: dict[str, Any] | None) -> AuditResult:
    media_id = choose_preview(listing)
    if media_id is None:
        return AuditResult("media_preview", "SKIP", "no eligible small indexed image")
    try:
        status, mime, data, _ = client.preview(media_id)
    except (OSError, ValueError, URLError, ssl.SSLError, TimeoutError):
        return AuditResult("media_preview", "FAIL", "cannot read image preview")
    if status in (404, 409, 415, 503):
        return AuditResult("media_preview", "SKIP", "preview unavailable / index changed")
    if status != 200:
        return AuditResult("media_preview", "FAIL", "HTTP " + str(status))
    magic = (data.startswith(b"\xff\xd8\xff") or
             data.startswith(b"\x89PNG\r\n\x1a\n") or
             (data.startswith(b"RIFF") and data[8:12] == b"WEBP"))
    if not mime.lower().startswith("image/") or not magic:
        return AuditResult("media_preview", "FAIL", "image media type/signature mismatch")
    return AuditResult("media_preview", "PASS", "small image header readable; decode unverified")


def run(client: ReadOnlyClient, *, sample_media: bool = False) -> list[AuditResult]:
    results: list[AuditResult] = []
    listing = None
    for path, label in HTML_CHECKS:
        try:
            stat, mime, body, excess = client.read(path, max_bytes=MAX_HTML)
            result = classify_html(label, stat, mime, body, excess)
        except (ValueError, OSError, URLError, ssl.SSLError, TimeoutError):
            result = AuditResult(label, "FAIL", "TLS/network/redirect error")
        results.append(result)
    for path, label, core in API_CHECKS:
        try:
            stat, mime, body, excess = client.read(path, max_bytes=MAX_JSON)
            result, data = classify_api(label, stat, mime, body, excess, optional=not core)
            if label == "dji_media":
                listing = data
        except (ValueError, OSError, URLError, ssl.SSLError, TimeoutError):
            result = AuditResult(label, "FAIL" if core else "SKIP",
                                 "TLS/network/source unavailable")
        results.append(result)
    if sample_media:
        results.append(check_preview(client, listing))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GET-only live HTTPS UI/API smoke")
    parser.add_argument("--instance-dir", type=Path,
                        default=Path.home() / "Projekte" / "AeroNexusAdvanced",
                        help="Deployed directory with existing .env and config/pki/ca.crt")
    parser.add_argument("--sample-media", action="store_true",
                        help="Also read <= 24 bytes of one eligible indexed small image")
    args = parser.parse_args(argv)
    try:
        client = configured_client(args.instance_dir.resolve())
    except (ValueError, OSError) as exc:
        print("ERROR: Configuration/TLS CA unavailable (" + type(exc).__name__ + ")")
        return 2
    print("AeroNexus positive HTTPS GET-only audit | certificate verification ON")
    results = run(client, sample_media=args.sample_media)
    for item in results:
        print(f"{item.state:4}  {item.label:26} {item.reason}")
    passed = sum(x.state == "PASS" for x in results)
    skipped = sum(x.state == "SKIP" for x in results)
    failed = sum(x.state == "FAIL" for x in results)
    print(f"Total: {passed} PASS, {skipped} SKIP, {failed} FAIL")
    print("No local changes, uploads, DJI commands or response bodies written.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
