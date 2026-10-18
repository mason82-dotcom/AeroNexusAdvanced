"""One-file-at-a-time gated Pilot 2 Cloud upload of offline-only DJI test fixtures.

Never imports flight tasks, publishes MQTT commands, or reaches any address
except the already configured fixed-loopback DJI Cloud server. The original
KMZ fixtures remain marked DO NOT FLY and are NOT flight certified.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import sys
from zipfile import BadZipFile, ZipFile
from io import BytesIO

import httpx

from .local_session import verify_session
from .local_waylines import (
    ORIGIN, Credentials, LocalWaylineError, credentials_path,
    load_credentials, read_waylines,
)
from .wpml_export import MODELS, WaypointMission, import_kmz

MODELS_ALLOWED = ("matrice4e", "matrice4t")
FILE_PREFIX = "AeroNexus_WPML_OFFLINE_ONLY_DO_NOT_FLY_"
MAX_KMZ_BYTES = 2 * 1024 * 1024
MAX_REPLY_BYTES = 65536


class FixtureUploadError(ValueError):
    """Fixed, non-sensitive error code, never a remote server response."""


@dataclass(frozen=True)
class FixturePlan:
    model: str
    filename: str
    sha256: str
    kmz: bytes = field(repr=False)

    @property
    def cloud_name(self) -> str:
        return self.filename[:-4]

    @property
    def model_key(self) -> str:
        drone, sub, _, _ = MODELS[self.model]
        return f"0-{drone}-{sub}"


def _private_file(path: Path, limit: int) -> bytes:
    """Reject links, special files, foreign ownership and loose permissions."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or not 0 < info.st_size <= limit):
            raise FixtureUploadError("invalid_private_fixture")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(limit + 1)
        if len(data) != info.st_size:
            raise FixtureUploadError("invalid_private_fixture")
        return data
    finally:
        os.close(fd)


def _expected_test_mission(model: str) -> WaypointMission:
    """Reconstruct generator inputs to rule out arbitrary missions."""
    return WaypointMission.model_validate({
        "name": "OFFLINE_ONLY_DO_NOT_FLY_" + model.upper(),
        "description": "Synthetic DJI WPML format inspection only; NEVER execute.",
        "drone_model": model,
        "altitude_m": 50.0,
        "speed_mps": 5.0,
        "takeoff_security_height_m": 20.0,
        "rth_height_m": 60.0,
        "finish_action": "goHome",
        "waypoints": [
            {"latitude": 49.15330, "longitude": 8.58400, "take_photo": True,
             "actions": [{"type": "startRecord"}]},
            {"latitude": 49.15345, "longitude": 8.58410,
             "actions": [{"type": "stopRecord"}]},
            {"latitude": 49.15360, "longitude": 8.58420},
        ],
    })


def prepare(directory: Path, model: str) -> FixturePlan:
    """Strictly load one of the two generated tests; no cloud or credential I/O."""
    if model not in MODELS_ALLOWED:
        raise FixtureUploadError("unsupported_model")
    directory = Path(directory)
    try:
        info = directory.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o700):
            raise FixtureUploadError("invalid_fixture_directory")
        manifest = json.loads(_private_file(
            directory / "offline-verification.json", 32768))
        if (not isinstance(manifest, dict)
                or manifest.get("kind") != "aeronexus-wpml-offline-acceptance-v1"
                or manifest.get("source") != "synthetic-test-data"
                or manifest.get("upload_performed") is not False
                or manifest.get("dji_pilot2_import_verified") is not False
                or manifest.get("flight_readiness_verified") is not False
                or not isinstance(manifest.get("samples"), list)
                or len(manifest["samples"]) != 2):
            raise FixtureUploadError("invalid_fixture_manifest")
        indexed = {row["model"]: row for row in manifest["samples"]
                   if isinstance(row, dict) and row.get("model") in MODELS_ALLOWED}
        if len(indexed) != 2 or set(indexed) != set(MODELS_ALLOWED):
            raise FixtureUploadError("invalid_fixture_manifest")
        for key, row in indexed.items():
            if (row.get("filename") != FILE_PREFIX + key.upper() + ".kmz"
                    or row.get("wpml_structure_verified") is not True
                    or row.get("own_round_trip_verified") is not True
                    or row.get("dji_pilot2_import_verified") is not False
                    or row.get("flight_readiness_verified") is not False
                    or row.get("waypoints") != 3
                    or row.get("camera_actions") !=
                    ["takePhoto", "startRecord", "stopRecord"]):
                raise FixtureUploadError("invalid_fixture_manifest")
        name = indexed[model]["filename"]
        blob = _private_file(directory / name, MAX_KMZ_BYTES)
        digest = sha256(blob).hexdigest()
        if digest != indexed[model].get("sha256"):
            raise FixtureUploadError("fixture_checksum_mismatch")
        with ZipFile(BytesIO(blob)) as archive:
            if set(archive.namelist()) != {
                "wpmz/template.kml", "wpmz/waylines.wpml"
            } or len(archive.infolist()) != 2 or archive.testzip() is not None:
                raise FixtureUploadError("invalid_fixture_archive")
        imported = import_kmz(blob)
        if imported.model_dump() != _expected_test_mission(model).model_dump():
            raise FixtureUploadError("unexpected_fixture_content")
        return FixturePlan(model=model, filename=name, sha256=digest, kmz=blob)
    except FixtureUploadError:
        raise
    except (OSError, ValueError, KeyError, TypeError, BadZipFile):
        raise FixtureUploadError("invalid_fixture") from None


async def check_cloud(plan: FixturePlan, creds: Credentials, *, transport=None) -> dict:
    """Read-only session check plus complete inventory; reject duplicate names."""
    try:
        await asyncio.wait_for(verify_session(creds, transport=transport), 8)
        inventory = await asyncio.wait_for(read_waylines(creds, transport=transport), 18)
    except (httpx.HTTPError, OSError, TimeoutError, LocalWaylineError):
        raise FixtureUploadError("cloud_preflight_unavailable") from None
    if inventory.get("state") != "connected" or inventory.get("pagination_complete") is not True:
        raise FixtureUploadError("cloud_inventory_incomplete")
    if any(row.get("name") == plan.cloud_name for row in inventory["waylines"]):
        raise FixtureUploadError("cloud_name_already_exists")
    return inventory


async def _check_post_reply(response: httpx.Response) -> None:
    if response.status_code != 200:
        raise FixtureUploadError("upload_http_error")
    content = bytearray()
    async for chunk in response.aiter_bytes():
        if len(content) + len(chunk) > MAX_REPLY_BYTES:
            raise FixtureUploadError("upload_invalid_response")
        content.extend(chunk)
    try:
        reply = json.loads(content)
    except (ValueError, UnicodeError, RecursionError):
        raise FixtureUploadError("upload_invalid_response") from None
    if not isinstance(reply, dict) or type(reply.get("code")) is not int:
        raise FixtureUploadError("upload_invalid_response")
    if reply["code"] != 0:
        raise FixtureUploadError("upload_rejected")


async def upload(plan: FixturePlan, creds: Credentials, *, transport=None) -> dict:
    """Single opt-in POST; any ambiguous result blocks retries."""
    if os.environ.get("AERONEXUS_PILOT_WAYLINE_UPLOAD_ENABLED") != "1":
        raise FixtureUploadError("upload_disabled")
    before = await check_cloud(plan, creds, transport=transport)
    original_ids = {row["wayline_id"] for row in before["waylines"]}
    url = (f"/wayline/api/v1/workspaces/{creds.workspace_id}"
           "/waylines/file/upload")
    try:
        async with httpx.AsyncClient(
            base_url=ORIGIN, timeout=25, trust_env=False,
            follow_redirects=False, transport=transport
        ) as client:
            async with client.stream(
                "POST", url, headers={"x-auth-token": creds.access_token},
                files={"file": (plan.filename, plan.kmz,
                                "application/vnd.google-earth.kmz")},
            ) as response:
                await _check_post_reply(response)
    except FixtureUploadError:
        raise FixtureUploadError("upload_rejected_or_outcome_unknown") from None
    except (httpx.HTTPError, OSError, TimeoutError):
        raise FixtureUploadError("upload_outcome_unknown") from None

    try:
        after = await asyncio.wait_for(read_waylines(creds, transport=transport), 18)
        matches = [row for row in after.get("waylines", [])
                   if row["name"] == plan.cloud_name
                   and row["wayline_id"] not in original_ids
                   and row.get("device_model_key") == plan.model_key]
        verified = (after.get("state") == "connected"
                    and after.get("pagination_complete") is True
                    and len(matches) == 1)
    except (httpx.HTTPError, OSError, TimeoutError, LocalWaylineError):
        verified = False
    return {"state": "registered" if verified else "submitted_unverified",
            "model": plan.model, "name": plan.cloud_name, "verified": verified}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True,
                        help="Existing private directory from offline KMZ generator")
    parser.add_argument("--model", choices=MODELS_ALLOWED, required=True)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check-cloud", action="store_true", help="GET only")
    action.add_argument("--apply", action="store_true", help="Actual one-file upload")
    args = parser.parse_args(argv)
    try:
        plan = prepare(args.source_dir, args.model)
        print("Validierte Testdatei:", plan.filename)
        print("SHA-256:", plan.sha256)
        print("Nur Pilot-2-Importtest, KEINE Flugfreigabe.")
        if not (args.check_cloud or args.apply):
            print("LOKALER DRY-RUN: kein Cloudzugriff, kein Upload.")
            return 0
        creds = load_credentials(credentials_path())
        if creds is None:
            raise FixtureUploadError("cloud_session_missing")
        if args.check_cloud:
            inventory = asyncio.run(check_cloud(plan, creds))
            print("Cloud-Verbindung gültig; Routen vollständig:",
                  inventory["reported_total"])
            print("GET ONLY: kein Upload.")
            return 0
        if os.environ.get("AERONEXUS_PILOT_WAYLINE_UPLOAD_ENABLED") != "1":
            raise FixtureUploadError("upload_disabled")
        if not sys.stdin.isatty():
            raise FixtureUploadError("interactive_confirmation_required")
        expected = "UPLOAD " + args.model.upper()
        confirmation = input(f'Einmalige Cloud-Übertragung: "{expected}" eingeben: ')
        if confirmation != expected:
            raise FixtureUploadError("not_confirmed")
        result = asyncio.run(upload(plan, creds))
        print("Cloudstatus:", result["state"], "| Name:", result["name"])
        if not result["verified"]:
            print("Ausgang unbestätigt: Cloud-Bibliothek prüfen, NICHT wiederholen.")
            return 2
        print("In Cloud-Bibliothek mit passendem Fluggerättyp nachgewiesen.")
        print("Kein Download auf die RC und keine Flugfreigabe erfolgt.")
        return 0
    except (FixtureUploadError, LocalWaylineError) as exc:
        print("Abbruch:", str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
