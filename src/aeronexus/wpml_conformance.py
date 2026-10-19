"""Read-only, bounded audit of AeroNexus DJI WPML KMZ files.

This checks the *editable local subset*, not general DJI WPML compliance,
firmware support, Pilot 2 importability, or flight readiness. Foreign and
WPML 1.0.6 documents fail closed without having their content rewritten.
No XML text, coordinates, IDs, mission titles, or tokens are reported.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import json
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET

from .wpml_export import (
    KML_NS, WPML_NS, MODELS, import_kmz, waypoints_for_export,
)

DJI_REFERENCE = (
    "https://developer.dji.com/doc/cloud-api-tutorial/en/"
    "api-reference/dji-wpml/common-element.html"
)
MEMBERS = ("wpmz/template.kml", "wpmz/waylines.wpml")
K = "{" + KML_NS + "}"
W = "{" + WPML_NS + "}"
MAX_KMZ_BYTES = 2 * 1024 * 1024
MAX_MEMBER_BYTES = 1024 * 1024
ALLOWED_SCHEMAS = {
    "1.0.2": WPML_NS,
    "1.0.6": "http://www.dji.com/wpmz/1.0.6",
}
LENS_MODELS = frozenset({"matrice4e", "matrice4t", "mavic3e", "mavic3t", "mavic3m"})
M4_MODELS = frozenset({"matrice4e", "matrice4t"})
SUPPORTED_ACTIONS = frozenset({
    "takePhoto", "startRecord", "stopRecord", "focus", "zoom",
    "gimbalRotate", "gimbalEvenlyRotate",
})


def _report() -> dict:
    return {
        "audit_profile": "aeronexus-offline-waypoint-v1",
        "status": "invalid",
        "editable_in_aeronexus": False,
        "wpml_schema": "unrecognized",
        "flight_compatibility_verified": False,
        "dji_pilot2_import_verified": False,
        "full_dji_wpml_conformance_verified": False,
        "waypoint_count": 0,
        "action_group_count": 0,
        "action_count": 0,
        "findings": [],
    }


def _finding(report: dict, code: str, severity: str) -> None:
    report["findings"].append({"code": code, "severity": severity})


def _uint16(node: ET.Element, name: str) -> int | None:
    raw = node.findtext(W + name)
    if raw is None or not raw.isascii() or not raw.isdigit():
        return None
    value = int(raw)
    return value if 0 <= value <= 65535 else None


def _wpml_schema(root: ET.Element) -> str:
    doc = root.find(K + "Document")
    if doc is None:
        return "unrecognized"
    matches = [
        version for version, namespace in ALLOWED_SCHEMAS.items()
        if doc.find("{" + namespace + "}missionConfig") is not None
    ]
    return matches[0] if len(matches) == 1 else "unrecognized"


def audit_kmz(blob: bytes) -> dict:
    """Inspect bytes without running commands or returning source XML.

    invalid = malformed or unsafe container/XML;
    unsupported = possibly valid WPML, but not safely editable here;
    supported_subset = canonical local export, not a DJI certification.
    """
    report = _report()
    if not isinstance(blob, bytes) or not 0 < len(blob) <= MAX_KMZ_BYTES:
        _finding(report, "INVALID_SIZE", "error")
        return report
    try:
        with ZipFile(BytesIO(blob)) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            if len(set(names)) != len(names):
                _finding(report, "DUPLICATE_ZIP_MEMBER", "error")
                return report
            if (
                any(
                    item.flag_bits & 1
                    or ((item.external_attr >> 16) & 0o170000) == 0o120000
                    or item.file_size > MAX_MEMBER_BYTES
                    for item in infos
                )
                or sum(item.file_size for item in infos) > MAX_KMZ_BYTES
            ):
                _finding(report, "UNSAFE_ZIP_MEMBER", "error")
                return report
            if sorted(names) != sorted(MEMBERS):
                report["status"] = "unsupported"
                _finding(report, "OUTSIDE_TWO_DOCUMENT_SUBSET", "unsupported")
                return report
            xml_docs = [archive.read(name) for name in MEMBERS]
        if any(b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper() for data in xml_docs):
            _finding(report, "XML_DTD_NOT_ALLOWED", "error")
            return report
        roots = [ET.fromstring(data) for data in xml_docs]
    except (BadZipFile, ET.ParseError, OSError, RuntimeError, EOFError, ValueError):
        _finding(report, "INVALID_ZIP_OR_XML", "error")
        return report

    if any(root.tag != K + "kml" for root in roots):
        report["status"] = "unsupported"
        _finding(report, "UNRECOGNIZED_KML_NAMESPACE", "unsupported")
        return report
    schemas = [_wpml_schema(root) for root in roots]
    if schemas[0] != schemas[1]:
        report["status"] = "unsupported"
        _finding(report, "MIXED_WPML_SCHEMAS", "unsupported")
        return report
    report["wpml_schema"] = schemas[0]
    if schemas[0] != "1.0.2":
        report["status"] = "unsupported"
        _finding(
            report,
            "WPML_106_READ_ONLY" if schemas[0] == "1.0.6"
            else "UNRECOGNIZED_WPML_SCHEMA",
            "unsupported",
        )
        return report

    # Importer proves full representation of BOTH documents by reconstructing
    # and comparing their canonical expanded XML signatures. In particular, it
    # refuses unknown actions/params and mixed legacy/new camera formats.
    try:
        mission = import_kmz(blob)
    except (ValueError, TypeError, OverflowError):
        report["status"] = "unsupported"
        _finding(report, "OUTSIDE_CANONICAL_EDITABLE_SUBSET", "unsupported")
        return report

    report["status"] = "supported_subset"
    report["editable_in_aeronexus"] = True
    waypoints = waypoints_for_export(mission)
    report["waypoint_count"] = len(waypoints)
    drone, subtype, payload, payload_subtype = MODELS[mission.drone_model]
    for root in roots:
        doc = root.find(K + "Document")
        config = doc.find(W + "missionConfig") if doc is not None else None
        if config is None:
            _finding(report, "MISSING_MISSION_CONFIG", "error")
            continue
        aircraft_info = config.find(W + "droneInfo")
        payload_info = config.find(W + "payloadInfo")
        if aircraft_info is None or payload_info is None:
            _finding(report, "MISSING_DEVICE_INFO", "error")
            continue
        if (
            aircraft_info.findtext(W + "droneEnumValue") != str(drone)
            or aircraft_info.findtext(W + "droneSubEnumValue") != str(subtype)
            or payload_info.findtext(W + "payloadEnumValue") != str(payload)
            or payload_info.findtext(W + "payloadSubEnumValue") != str(payload_subtype)
            or payload_info.findtext(W + "payloadPositionIndex") != "0"
        ):
            _finding(report, "DEVICE_PROFILE_MISMATCH", "error")
        folder = doc.find(K + "Folder")
        if folder is None:
            _finding(report, "MISSING_WAYLINE_FOLDER", "error")
            continue
        points = folder.findall(K + "Placemark")
        if len(points) != len(waypoints):
            _finding(report, "WAYPOINT_COUNT_MISMATCH", "error")
        ids = set()
        for index, point in enumerate(points):
            for group in point.findall(W + "actionGroup"):
                report["action_group_count"] += 1
                group_id = _uint16(group, "actionGroupId")
                start = _uint16(group, "actionGroupStartIndex")
                end = _uint16(group, "actionGroupEndIndex")
                if (
                    group_id is None or group_id in ids
                    or start is None or end is None
                    or start > end or end >= len(points)
                    or group.findtext(W + "actionGroupMode") != "sequence"
                ):
                    _finding(report, "INVALID_ACTION_GROUP", "error")
                else:
                    ids.add(group_id)
                trigger = group.findtext(W + "actionTrigger/" + W + "actionTriggerType")
                actions = group.findall(W + "action")
                action_ids = set()
                for action in actions:
                    report["action_count"] += 1
                    action_id = _uint16(action, "actionId")
                    if action_id is None or action_id in action_ids:
                        _finding(report, "INVALID_ACTION_ID", "error")
                    else:
                        action_ids.add(action_id)
                    kind = action.findtext(W + "actionActuatorFunc")
                    if kind not in SUPPORTED_ACTIONS:
                        _finding(report, "UNSUPPORTED_ACTION", "error")
                        continue
                    expected_trigger = (
                        "betweenAdjacentPoints" if kind == "gimbalEvenlyRotate"
                        else "reachPoint"
                    )
                    if (
                        trigger != expected_trigger
                        or start != index
                        or end != index + (kind == "gimbalEvenlyRotate")
                    ):
                        _finding(report, "INVALID_ACTION_TRIGGER_OR_SPAN", "error")
                    params = action.find(W + "actionActuatorFuncParam")
                    if params is None or params.findtext(W + "payloadPositionIndex") != "0":
                        _finding(report, "INVALID_ACTION_PAYLOAD", "error")
                        continue
                    if kind in ("takePhoto", "startRecord"):
                        lens = params.findtext(W + "payloadLensIndex")
                        flag = params.findtext(W + "useGlobalPayloadLensIndex")
                        expected_lens = "wide" if mission.drone_model in M4_MODELS else None
                        expected_flag = "0" if mission.drone_model in LENS_MODELS else None
                        # The strict importer also permits the ENTIRE previous
                        # AeroNexus legacy camera representation, for reimport only.
                        legacy = flag is None and lens is None
                        if not legacy and (lens != expected_lens or flag != expected_flag):
                            _finding(report, "INVALID_CAMERA_LENS_SELECTION", "error")
                        if legacy and mission.drone_model in LENS_MODELS:
                            _finding(report, "LEGACY_CAMERA_FIELDS", "advisory")
        # DJI's current table calls headingPathMode required; sample exports
        # differ, so classify the omission as unresolved, not an invalid flight.
        if folder.find(W + "globalWaypointHeadingParam") is not None:
            heading = folder.find(W + "globalWaypointHeadingParam")
            if heading.find(W + "waypointHeadingPathMode") is None:
                _finding(report, "HEADING_PATH_MODE_INTEROP_UNVERIFIED", "advisory")

    if any(item["severity"] == "error" for item in report["findings"]):
        report["status"] = "unsupported"
        report["editable_in_aeronexus"] = False
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only local WPML audit; never validates flight readiness"
    )
    parser.add_argument("kmz", type=Path, help="Path to a local KMZ file")
    args = parser.parse_args(argv)
    try:
        if args.kmz.is_symlink() or not args.kmz.is_file():
            raise OSError("not a regular file")
        with args.kmz.open("rb") as source:
            blob = source.read(MAX_KMZ_BYTES + 1)
        result = audit_kmz(blob)
    except OSError:
        result = _report()
        _finding(result, "UNREADABLE_FILE", "error")
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    return 0 if result["editable_in_aeronexus"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
