#!/usr/bin/env python3
"""Prepare two synthetic DJI-WPML KMZ files for OFFLINE Pilot 2 inspection.

There is intentionally no DJI/MQTT/HTTP client, mission upload, flight
command, production workspace access, or use of local credentials.  The KMZ
files are NOT flight-tested or cleared for execution.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from aeronexus.wpml_export import (
    KML_NS, MODELS, WPML_NS, WaypointMission, export_kmz, import_kmz,
)

ARCHIVE_MEMBERS = frozenset({"wpmz/template.kml", "wpmz/waylines.wpml"})
SAMPLE_MODELS = ("matrice4e", "matrice4t")
TIMESTAMP_MS = 1792368000000  # fixed XML timestamp; ZIP member timestamps can vary
PREFIX = "AeroNexus_WPML_OFFLINE_ONLY_DO_NOT_FLY"
K = "{" + KML_NS + "}"
W = "{" + WPML_NS + "}"


class OfflineAcceptanceError(ValueError):
    """A local test file failed a strictly offline verification."""


def sample_mission(model: str) -> WaypointMission:
    """Synthetic coordinates are test inputs, not a surveyed flight area."""
    if model not in SAMPLE_MODELS:
        raise OfflineAcceptanceError("Unsupported offline sample model")
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


def verify_kmz(blob: bytes, expected: WaypointMission) -> dict:
    """Validate exported bytes independently of the exporter-facing tests.

    No values from coordinates, stored media, accounts or credentials are
    returned in the report.  This is structural, not DJI Pilot 2 acceptance.
    """
    if not isinstance(blob, bytes) or not blob:
        raise OfflineAcceptanceError("Missing KMZ data")
    try:
        imported = import_kmz(blob)
        if imported.model_dump() != expected.model_dump():
            raise OfflineAcceptanceError("Own KMZ import/export does not round-trip")
        with ZipFile(__import__("io").BytesIO(blob)) as archive:
            if len(archive.infolist()) != 2 or set(archive.namelist()) != ARCHIVE_MEMBERS:
                raise OfflineAcceptanceError("KMZ members differ from WPML subset")
            if archive.testzip() is not None:
                raise OfflineAcceptanceError("KMZ CRC verification failed")
            documents = [ET.fromstring(archive.read(filename))
                         for filename in ("wpmz/template.kml", "wpmz/waylines.wpml")]
    except OfflineAcceptanceError:
        raise
    except (OSError, ValueError, ET.ParseError) as exc:
        raise OfflineAcceptanceError("Generated KMZ failed offline validation") from exc

    aircraft, sub, payload, payload_sub = MODELS[expected.drone_model]
    for document in documents:
        if document.tag != K + "kml":
            raise OfflineAcceptanceError("Unexpected KML namespace")
        config = document.find(K + "Document/" + W + "missionConfig")
        if config is None:
            raise OfflineAcceptanceError("Missing mission configuration")
        requirements = {
            "droneEnumValue": str(aircraft),
            "droneSubEnumValue": str(sub),
            "payloadEnumValue": str(payload),
            "payloadSubEnumValue": str(payload_sub),
            "payloadPositionIndex": "0",
        }
        for name, value in requirements.items():
            if config.findtext(".//" + W + name) != value:
                raise OfflineAcceptanceError("Aircraft/payload does not match offline test")
        points = document.findall(".//" + K + "Placemark")
        if len(points) != 3:
            raise OfflineAcceptanceError("Wrong offline waypoint count")
        if [p.findtext(W + "index") for p in points] != ["0", "1", "2"]:
            raise OfflineAcceptanceError("Invalid waypoint indexes")
        operations = {}
        for point in points:
            for group in point.findall(W + "actionGroup"):
                action = group.find(W + "action")
                if action is None:
                    raise OfflineAcceptanceError("Missing action container")
                function = action.findtext(W + "actionActuatorFunc")
                if function in operations:
                    raise OfflineAcceptanceError("Unexpected duplicate camera operation")
                operations[function] = action.find(W + "actionActuatorFuncParam")
        if set(operations) != {"takePhoto", "startRecord", "stopRecord"}:
            raise OfflineAcceptanceError("Missing or unexpected camera operation")
        for function in ("takePhoto", "startRecord"):
            params = operations[function]
            if params is None or params.findtext(W + "payloadLensIndex") != "wide":
                raise OfflineAcceptanceError("Matrice 4 lens is not explicitly wide")
            if params.findtext(W + "useGlobalPayloadLensIndex") != "0":
                raise OfflineAcceptanceError("Unexpected global lens selector")
            if params.findtext(W + "payloadPositionIndex") != "0":
                raise OfflineAcceptanceError("Wrong payload mount index")
        if operations["stopRecord"] is None:
            raise OfflineAcceptanceError("Missing stop-record parameters")

    return {
        "model": expected.drone_model,
        "filename": PREFIX + "_" + expected.drone_model.upper() + ".kmz",
        "sha256": sha256(blob).hexdigest(),
        "waypoints": 3,
        "camera_actions": ["takePhoto", "startRecord", "stopRecord"],
        "wpml_structure_verified": True,
        "own_round_trip_verified": True,
        "dji_pilot2_import_verified": False,
        "flight_readiness_verified": False,
    }


def _write_new(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)


def generate_samples(output_dir: Path) -> dict:
    """Create a NEW private directory; never replace any existing file."""
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError("Refusing an existing output directory")
    output_dir.parent.resolve(strict=True)
    payloads = []
    for model in SAMPLE_MODELS:
        mission = sample_mission(model)
        blob = export_kmz(mission, timestamp_ms=TIMESTAMP_MS)
        metadata = verify_kmz(blob, mission)
        payloads.append((metadata["filename"], blob, metadata))
    report = {
        "kind": "aeronexus-wpml-offline-acceptance-v1",
        "source": "synthetic-test-data",
        "network_access_required": False,
        "upload_performed": False,
        "dji_pilot2_import_verified": False,
        "flight_readiness_verified": False,
        "warning": "OFFLINE TEST ONLY. Coordinates are synthetic. DO NOT FLY.",
        "samples": [entry for _, _, entry in payloads],
    }
    report_bytes = (json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    output_dir.mkdir(mode=0o700)
    created = []
    try:
        for name, blob, _ in payloads:
            target = output_dir / name
            _write_new(target, blob)
            created.append(target)
        target = output_dir / "offline-verification.json"
        _write_new(target, report_bytes)
        created.append(target)
    except Exception:
        for target in created:
            target.unlink(missing_ok=True)
        output_dir.rmdir()
        raise
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="NEW directory, not an existing production or cloud location")
    args = parser.parse_args(argv)
    try:
        report = generate_samples(args.output_dir)
    except (ValueError, OSError) as exc:
        print("WPML OFFLINE ERROR: " + str(exc), file=sys.stderr)
        return 1
    print("WPML OFFLINE ONLY: " + str(len(report["samples"])) + " samples written")
    print("Output: " + str(args.output_dir))
    print("Pilot 2 import: NOT TESTED; mission flight: NOT PERMITTED BY THIS CHECK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
