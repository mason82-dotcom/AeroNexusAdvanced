"""Opt-in local Pilot 2 KMZ import, via the DJI Demo's direct upload API.

Unlike the existing local_waylines reader, this module can WRITE to DJI's local
Cloud *only* when invoked with --apply, with an explicit environment gate and
interactive confirmation. It is not routed through FastAPI or MQTT.
"""
import argparse
import asyncio
from dataclasses import dataclass, field
import json
import os
import sys
import time
from uuid import UUID, uuid4

import httpx

from .local_session import verify_session
from .local_waylines import (ORIGIN, Credentials, LocalWaylineError,
                             credentials_path, load_credentials, read_waylines)
from .studio_workspace import Workspace, WorkspaceError
from .wpml_export import MODELS, WaypointMission, export_kmz, import_kmz

MAX_KMZ_BYTES = 2 * 1024 * 1024
MAX_REPLY_BYTES = 65536
UPLOAD_TIMEOUT_SECONDS = 25


class UploadError(ValueError):
    """Fixed non-sensitive code, never a remote response body."""


@dataclass(frozen=True)
class UploadPlan:
    mission_id: str
    name: str
    drone_model: str
    points: int
    filename: str
    kmz: bytes = field(repr=False)


def prepare(mission_id: str, *, workspace: Workspace | None = None,
            timestamp_ms: int | None = None, nonce: str | None = None) -> UploadPlan:
    """Local-only build with a fresh filename; no network or cloud writes."""
    try:
        mission_id = str(UUID(mission_id))
        store = workspace or Workspace()
        mission = WaypointMission.model_validate(store.get_mission(mission_id)["mission"])
        # No server-provided or user-provided object key/path is ever accepted.
        suffix = nonce or uuid4().hex[:12]
        if len(suffix) != 12 or any(c not in "0123456789abcdef" for c in suffix):
            raise UploadError("invalid_nonce")
        filename = f"aeronexus-{mission_id}-{suffix}.kmz"
        blob = export_kmz(mission, timestamp_ms=timestamp_ms if timestamp_ms is not None
                          else int(time.time() * 1000))
        if len(blob) > MAX_KMZ_BYTES:
            raise UploadError("kmz_too_large")
        # Ensures our exported WPML can also be strictly read by our own parser.
        reloaded = import_kmz(blob)
        if reloaded.model_dump() != mission.model_dump():
            raise UploadError("kmz_roundtrip_mismatch")
        return UploadPlan(mission_id=mission_id, name=mission.name,
                          drone_model=mission.drone_model,
                          points=len(mission.waypoints), filename=filename, kmz=blob)
    except UploadError:
        raise
    except (ValueError, WorkspaceError, OSError, KeyError):
        raise UploadError("invalid_mission") from None


async def _upload_response(response: httpx.Response) -> None:
    """Parse bounded Java HttpResultResponse, never expose remote error text."""
    if response.status_code != 200:
        raise UploadError("upload_http_error")
    content = bytearray()
    async for chunk in response.aiter_bytes():
        if len(content) + len(chunk) > MAX_REPLY_BYTES:
            raise UploadError("upload_invalid_response")
        content.extend(chunk)
    try:
        payload = json.loads(content)
    except (ValueError, UnicodeError, RecursionError):
        raise UploadError("upload_invalid_response") from None
    if not isinstance(payload, dict) or type(payload.get("code")) is not int:
        raise UploadError("upload_invalid_response")
    if payload["code"] != 0:
        raise UploadError("upload_rejected")


def require_expected_model(plan: UploadPlan, expected_model: str | None) -> str:
    """Block an accidental upload of a route for a different aircraft."""
    if expected_model not in MODELS:
        raise UploadError("expected_model_required")
    if plan.drone_model != expected_model:
        raise UploadError("model_mismatch")
    drone, subtype, _, _ = MODELS[expected_model]
    return f"0-{drone}-{subtype}"


async def check_cloud(plan: UploadPlan, credentials: Credentials, *,
                      transport=None) -> dict:
    """Read-only authenticated preflight, no cloud write or storage credentials."""
    try:
        await asyncio.wait_for(verify_session(credentials, transport=transport), 8)
        before = await asyncio.wait_for(read_waylines(credentials, transport=transport), 18)
    except (httpx.HTTPError, OSError, TimeoutError, LocalWaylineError):
        raise UploadError("preflight_unavailable") from None
    if before.get("state") != "connected" or before.get("pagination_complete") is not True:
        raise UploadError("inventory_incomplete")
    name = plan.filename[:-4]
    if any(item.get("name") == name for item in before["waylines"]):
        raise UploadError("name_conflict")
    return before


async def upload(plan: UploadPlan, credentials: Credentials, *,
                 expected_model: str | None = None, transport=None) -> dict:
    """One explicit multipart POST, no redirects or retries, after strict GETs.

    A lost response after the write is ambiguous: never resend automatically.
    """
    if os.environ.get("AERONEXUS_PILOT_WAYLINE_UPLOAD_ENABLED") != "1":
        raise UploadError("upload_disabled")
    model_key = require_expected_model(plan, expected_model)
    before = await check_cloud(plan, credentials, transport=transport)
    prior_ids = {item["wayline_id"] for item in before["waylines"]}
    cloud_name = plan.filename[:-4]

    path = f"/wayline/api/v1/workspaces/{credentials.workspace_id}/waylines/file/upload"
    try:
        async with httpx.AsyncClient(base_url=ORIGIN, timeout=UPLOAD_TIMEOUT_SECONDS,
                                     follow_redirects=False, trust_env=False,
                                     transport=transport) as client:
            async with client.stream(
                "POST", path, headers={"x-auth-token": credentials.access_token},
                files={"file": (plan.filename, plan.kmz, "application/vnd.google-earth.kmz")},
            ) as response:
                await _upload_response(response)
    except UploadError:
        # The remote service may have written the file and failed afterwards.
        raise UploadError("upload_rejected_or_outcome_unknown") from None
    except (httpx.HTTPError, OSError, TimeoutError):
        raise UploadError("upload_outcome_unknown") from None

    try:
        after = await asyncio.wait_for(read_waylines(credentials, transport=transport), 18)
        verified = False
        if after.get("state") == "connected" and after.get("pagination_complete") is True:
            matches = [item for item in after.get("waylines", [])
                       if item["name"] == cloud_name
                       and item["wayline_id"] not in prior_ids
                       and item.get("device_model_key") == model_key]
            verified = len(matches) == 1
    except (httpx.HTTPError, OSError, TimeoutError, LocalWaylineError):
        verified = False
    return {"state": "registered" if verified else "submitted_unverified",
            "name": cloud_name, "verified": verified}


def main() -> int:
    parser = argparse.ArgumentParser(description="AeroNexus mission -> local DJI Pilot 2 library")
    parser.add_argument("--mission", required=True, help="UUID of a saved AeroNexus mission")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--apply", action="store_true", help="Explicit real cloud upload")
    action.add_argument("--check-cloud", action="store_true",
                        help="Read-only cloud session and inventory preflight")
    parser.add_argument("--expect-model", choices=tuple(MODELS),
                        help="Required for --apply: expected exact aircraft profile")
    args = parser.parse_args()
    try:
        plan = prepare(args.mission)
        print("Mission:", plan.name)
        print("Profil:", plan.drone_model, "| Wegpunkte:", plan.points)
        print("KMZ:", len(plan.kmz), "Bytes")
        print("Vorgesehener Cloud-Name:", plan.filename[:-4])
        if args.expect_model:
            require_expected_model(plan, args.expect_model)
        elif args.apply:
            raise UploadError("expected_model_required")
        if args.check_cloud:
            credentials = load_credentials(credentials_path())
            if credentials is None:
                raise UploadError("session_missing")
            before = asyncio.run(check_cloud(plan, credentials))
            print("Cloud-Sitzung gültig; Waylines vollständig:", before["reported_total"])
            print("READ ONLY: kein Upload.")
            return 0
        if not args.apply:
            print("DRY RUN: kein Netzwerkzugriff, kein Upload. --apply für explizite Übertragung.")
            return 0
        if os.environ.get("AERONEXUS_PILOT_WAYLINE_UPLOAD_ENABLED") != "1":
            raise UploadError("upload_disabled")
        if not sys.stdin.isatty():
            raise UploadError("interactive_confirmation_required")
        confirmation = input('Zum Hochladen exakt "UPLOAD" eingeben: ')
        if confirmation != "UPLOAD":
            raise UploadError("not_confirmed")
        credentials = load_credentials(credentials_path())
        if credentials is None:
            raise UploadError("session_missing")
        result = asyncio.run(upload(plan, credentials, expected_model=args.expect_model))
        print("Serverergebnis:", result["state"], "| Cloud-Name:", result["name"])
        if not result["verified"]:
            print("Antwort nicht abschließend bestätigt; Bibliothek prüfen, NICHT erneut hochladen.")
            return 2
        print("Die Cloud-Wayline wurde in der lokalen Bibliothek nachgewiesen.")
        return 0
    except (UploadError, LocalWaylineError, WorkspaceError) as exc:
        print("Abbruch:", str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
