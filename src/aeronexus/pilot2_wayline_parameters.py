"""Opt-in, GET-only DJI Pilot 2 WPML parameter audit; no flight controls.

Raw KMZ is confined to process memory. Output never includes route names, IDs,
coordinates, raw XML, signed URLs, serial numbers or credentials. Parameter
comparison is deliberately partial and only for a single identical wayline.
"""
import argparse
import asyncio
from decimal import Decimal, InvalidOperation
from io import BytesIO
import json
import re
from zipfile import BadZipFile, ZipFile

import httpx

from .local_waylines import (
    LocalWaylineError, credentials_path, load_credentials, read_waylines,
)
from .pilot2_wayline_compare import (
    compare_geometry, read_local_mission,
)
from .pilot2_wayline_preview import (
    MAX_ELEMENTS, MAX_FEATURES, MAX_KMZ, MAX_MEMBER, _coordinate,
    _download_kmz, _xml_root, parse_preview_kmz,
)
from .studio_workspace import WorkspaceError
from .wpml_export import KML_NS, WPML_NS, MODELS, WaypointMission, _num, waypoints_for_export

K = "{" + KML_NS + "}"
W = "{" + WPML_NS + "}"
# DJI's published WPML sample declares 1.0.2; 1.0.6 occurs in
# newer Pilot 2-compatible KMZ files but is NOT a semantic equivalence proof.
# Never accept arbitrary XML namespaces based on element local names alone.
KNOWN_WPML_SCHEMAS = {
    "1.0.2": WPML_NS,
    "1.0.6": "http://www.dji.com/wpmz/1.0.6",
}
FIELDS = (
    "flyToWaylineMode", "finishAction", "exitOnRCLost",
    "executeRCLostAction", "takeOffSecurityHeight",
    "globalTransitionalSpeed", "globalRTHHeight",
)
MODES = {"relativeToStartPoint", "WGS84", "realTimeFollowSurface"}
# Known names only: the source enum from DJI's WPML action common elements.
# This is a read-only classification, not firmware/action compatibility validation.
DOCUMENTED_ACTION_TYPES = frozenset({
    "takePhoto", "startRecord", "stopRecord", "focus", "zoom",
    "customDirName", "gimbalRotate", "rotateYaw", "hover",
    "gimbalEvenlyRotate", "accurateShoot", "orientedShoot", "panoShot",
    "recordPointCloud",
})
MAX_ACTIONS = 10000
_MODEL_PART = re.compile(r"[0-9]{1,5}\Z")


def _child_text(parent, tag, wpml_prefix=W):
    if parent is None:
        return None
    elems = parent.findall(wpml_prefix + tag)
    if len(elems) != 1 or elems[0].text is None:
        return None
    value = elems[0].text.strip()
    return value if 0 < len(value) <= 120 else None


def _number(value):
    if value is None or len(value) > 60:
        return None
    try:
        num = Decimal(value)
    except (InvalidOperation, ValueError):
        return None
    return num if num.is_finite() and abs(num) <= 1000000000 else None


def _model_key(node, wpml_prefix=W):
    a = _child_text(node, "droneEnumValue", wpml_prefix)
    b = _child_text(node, "droneSubEnumValue", wpml_prefix)
    return f"0-{a}-{b}" if a and b and _MODEL_PART.fullmatch(a) and _MODEL_PART.fullmatch(b) else None


def _read_wpml_root(kmz: bytes):
    if not isinstance(kmz, bytes) or not 0 < len(kmz) <= MAX_KMZ:
        raise LocalWaylineError("invalid_archive")
    try:
        with ZipFile(BytesIO(kmz)) as archive:
            infos = archive.infolist()
            if (len(infos) > 20 or len({item.filename for item in infos}) != len(infos)
                    or any(item.flag_bits & 1 or item.file_size > MAX_MEMBER
                           or (item.external_attr >> 16) & 0o170000 == 0o120000
                           for item in infos)
                    or sum(item.file_size for item in infos) > MAX_KMZ):
                raise LocalWaylineError("invalid_archive")
            if "wpmz/waylines.wpml" not in archive.namelist():
                raise LocalWaylineError("unsupported_geometry")
            with archive.open("wpmz/waylines.wpml") as stream:
                data = stream.read(MAX_MEMBER + 1)
            if len(data) > MAX_MEMBER:
                raise LocalWaylineError("invalid_archive")
    except (BadZipFile, OSError, RuntimeError, EOFError):
        raise LocalWaylineError("invalid_archive") from None
    return _xml_root(data)


def _read_xml(kmz: bytes):
    root = _read_wpml_root(kmz)
    if root.tag != K + "kml":
        raise LocalWaylineError("unsupported_geometry")
    doc = root.find(K + "Document")
    if doc is None:
        raise LocalWaylineError("unsupported_geometry")
    return doc


def _ns_class(tag, target):
    if not isinstance(tag, str):
        return "unknown"
    if tag == "{" + target + "}" + tag.rsplit("}", 1)[-1]:
        return "standard"
    if not tag.startswith("{"):
        return "unqualified"
    return "nonstandard"


def classify_wpml_structure(kmz: bytes) -> dict:
    """Report only structural categories, never tag contents, namespaces or positions.

    Inspect missing qualified/recursive XML elements without lowering semantic
    validation. A nonstandard namespace is never silently treated as DJI WPML.
    """
    root = _read_wpml_root(kmz)
    elements = list(root.iter())
    if len(elements) > 25000:
        raise LocalWaylineError("invalid_archive")
    from .pilot2_wayline_preview import _tag
    direct_docs = [item for item in root if _tag(item) == "Document"]
    all_docs = [item for item in elements if _tag(item) == "Document"]
    doc = direct_docs[0] if len(direct_docs) == 1 else None
    descendants = list(doc.iter()) if doc is not None else []
    direct_configs = [item for item in doc if _tag(item) == "missionConfig"] if doc is not None else []
    configs = [item for item in descendants if _tag(item) == "missionConfig"]
    direct_folders = [item for item in doc if _tag(item) == "Folder"] if doc is not None else []
    all_folders = [item for item in descendants if _tag(item) == "Folder"]
    direct_wpml_config = doc.find(W + "missionConfig") if doc is not None else None
    recognized_versions = [v for v, ns in KNOWN_WPML_SCHEMAS.items()
                           if configs and configs[0].tag == "{" + ns + "}missionConfig"]
    detected_schema = recognized_versions[0] if len(recognized_versions) == 1 else "unknown"
    direct_qualified_folders = doc.findall(K + "Folder") if doc is not None else []
    spots = [item for item in descendants if _tag(item) == "Placemark"]
    points = [item for item in descendants if _tag(item) == "Point"]
    coords = [item for item in descendants if _tag(item) == "coordinates"]
    # Exact parser compatibility only; do not expose root tags or namespace URIs.
    qualified_doc = root.find(K + "Document") if root.tag == K + "kml" else None
    strict_ok = bool(qualified_doc is not None
                     and qualified_doc.find(W + "missionConfig") is not None
                     and 1 <= len(qualified_doc.findall(K + "Folder")) <= MAX_FEATURES)
    if root.tag != K + "kml":
        reason = "root_namespace"
    elif qualified_doc is None:
        reason = "document_namespace_or_nesting"
    elif direct_wpml_config is None:
        reason = "mission_config_namespace_or_missing"
    elif not direct_qualified_folders:
        reason = "folder_namespace_or_nesting"
    elif len(direct_qualified_folders) > MAX_FEATURES:
        reason = "too_many_direct_folders"
    else:
        # The strict parser additionally requires direct Point/coordinates.
        direct_points = 0
        for folder in direct_qualified_folders:
            for place in folder.findall(K + "Placemark"):
                point = place.find(K + "Point")
                if point is not None and point.find(K + "coordinates") is not None:
                    direct_points += 1
        reason = "point_coordinate_namespace_or_nesting" if direct_points < len(spots) else "structurally_compatible"
    return {
        "root_namespace": _ns_class(root.tag, KML_NS),
        "direct_document_count": len(direct_docs),
        "document_count": len(all_docs),
        "document_namespace": _ns_class(doc.tag, KML_NS) if doc is not None else None,
        "direct_mission_config_count": len(direct_configs),
        "mission_config_count": len(configs),
        "mission_config_namespace": _ns_class(configs[0].tag, WPML_NS) if configs else None,
        "recognized_wpml_schema_version": detected_schema,
        "read_only_schema_supported": detected_schema in KNOWN_WPML_SCHEMAS,
        "direct_folder_count": len(direct_folders),
        "folder_count": len(all_folders),
        "folder_namespace": _ns_class(all_folders[0].tag, KML_NS) if all_folders else None,
        "placemark_count": len(spots),
        "point_count": len(points),
        "coordinate_element_count": len(coords),
        "strict_parser_gate": reason,
        "strict_header_compatible": strict_ok,
        "full_content_verified": False,
    }


async def diagnose_structure(*, limit=8, inventory_reader=None, kmz_reader=None,
                             credentials_loader=None):
    """Classify actual Pilot 2 KMZ layout, with no IDs, names or coordinates."""
    if type(limit) is not int or not 1 <= limit <= 8:
        raise ValueError("invalid limit")
    reader = inventory_reader or read_waylines
    downloader = kmz_reader or _download_kmz
    loader = credentials_loader or load_credentials
    credentials = loader(credentials_path())
    if credentials is None:
        return {"inventory_state": "not_configured", "results": []}
    inventory = await asyncio.wait_for(reader(credentials), timeout=15)
    if (inventory.get("state") != "connected"
            or inventory.get("workspace_id") != credentials.workspace_id
            or not inventory.get("pagination_complete")):
        return {"inventory_state": "incomplete_inventory", "results": []}
    results = []
    for index, route in enumerate(inventory["waylines"][:limit], start=1):
        try:
            kmz = await asyncio.wait_for(downloader(
                credentials, route["wayline_id"]), timeout=22)
            results.append({"index": index, "state": "connected",
                            **classify_wpml_structure(kmz)})
        except LocalWaylineError as exc:
            allowed = {"invalid_archive", "storage_unavailable", "authentication_required",
                       "storage_origin_rejected", "unsupported_geometry"}
            results.append({"index": index, "state": str(exc) if str(exc) in allowed else "unavailable"})
        except (httpx.HTTPError, OSError, TimeoutError):
            results.append({"index": index, "state": "unavailable"})
    return {"inventory_state": "connected", "reported_total": inventory.get("reported_total"),
            "checked": len(results), "results": results}


def _action_counts(values):
    """Only expose allowlisted DJI enum names and counts, never upstream text."""
    counts = {}
    unknown = 0
    for value in values:
        if value in DOCUMENTED_ACTION_TYPES:
            counts[value] = counts.get(value, 0) + 1
        else:
            unknown += 1
    return dict(sorted(counts.items())), unknown


def parse_parameter_audit(kmz: bytes) -> dict:
    """Bounded, allowlisted, position-free WPML audit over actual executable Folders."""
    doc = _read_xml(kmz)
    # Only exact namespace URIs in a deliberately small read-only allowlist.
    # Duplicate/mixed schemas are ambiguous and fail closed.
    matches = [(version, doc.find("{" + namespace + "}missionConfig"))
               for version, namespace in KNOWN_WPML_SCHEMAS.items()]
    present = [(version, node) for version, node in matches if node is not None]
    folders = doc.findall(K + "Folder")
    if len(present) != 1 or not 1 <= len(folders) <= MAX_FEATURES:
        raise LocalWaylineError("unsupported_geometry")
    schema_version, config = present[0]
    wpml_prefix = "{" + KNOWN_WPML_SCHEMAS[schema_version] + "}"

    drone = config.find(wpml_prefix + "droneInfo")
    payload = config.find(wpml_prefix + "payloadInfo")
    global_fields = {field: _child_text(config, field, wpml_prefix) for field in FIELDS}
    route_info = []
    total = 0
    action_total = 0
    for folder in folders:
        places = folder.findall(K + "Placemark")
        total += len(places)
        if total > MAX_ELEMENTS:
            raise LocalWaylineError("invalid_archive")
        waypoints, photo_count, other_action_count = [], 0, 0
        route_action_values = []
        start_groups = folder.findall(wpml_prefix + "startActionGroup")
        if len(start_groups) > 1:
            raise LocalWaylineError("unsupported_geometry")
        start_action_values = [
            elem.text.strip() if elem.text else None
            for group in start_groups
            for elem in group.findall(".//" + wpml_prefix + "actionActuatorFunc")
        ]
        action_total += len(start_action_values)
        if action_total > MAX_ACTIONS:
            raise LocalWaylineError("invalid_archive")
        for place in places:
            point = place.find(K + "Point")
            coords = point.find(K + "coordinates") if point is not None else None
            if coords is None or coords.text is None:
                raise LocalWaylineError("unsupported_geometry")
            # Validate values, but coordinates are NEVER returned in the audit.
            _coordinate(coords.text)
            action_nodes = place.findall(".//" + wpml_prefix + "action")
            actions = [
                item.text.strip() if item.text else None
                for item in place.findall(".//" + wpml_prefix + "actionActuatorFunc")
            ]
            action_structure_unknown = (
                len(action_nodes) != len(actions)
                or (bool(place.findall(".//" + wpml_prefix + "actionGroup")) and not action_nodes)
            )
            action_total += len(actions)
            if action_total > MAX_ACTIONS:
                raise LocalWaylineError("invalid_archive")
            route_action_values.extend(actions)
            photo_count += actions.count("takePhoto")
            other_action_count += len(actions) - actions.count("takePhoto")
            waypoints.append({
                "height": _number(_child_text(place, "executeHeight", wpml_prefix)),
                "speed": _number(_child_text(place, "waypointSpeed", wpml_prefix)),
                "photo_only": actions == ["takePhoto"],
                "no_actions": len(actions) == 0,
                "action_count": len(actions),
                "action_structure_unknown": action_structure_unknown,
            })
        per_route_counts, per_route_unknown = _action_counts(route_action_values)
        start_counts, start_unknown = _action_counts(start_action_values)
        mode = _child_text(folder, "executeHeightMode", wpml_prefix)
        route_info.append({
            "height_mode": mode if mode in MODES else "unknown",
            "speed": _number(_child_text(folder, "autoFlightSpeed", wpml_prefix)),
            "waypoints": waypoints,
            "photo_count": photo_count,
            "other_action_count": other_action_count,
            "start_actions_present": bool(start_groups),
            "action_type_counts": per_route_counts,
            "unrecognized_action_count": per_route_unknown,
            "start_action_type_counts": start_counts,
            "unrecognized_start_action_count": start_unknown,
            "start_action_count": len(start_action_values),
        })
    return {
        "wpml_schema_version": schema_version,
        "wpml_model_key": _model_key(drone, wpml_prefix),
        "wpml_payload_key": _child_text(payload, "payloadEnumValue", wpml_prefix),
        "global_fields": global_fields,
        "routes": route_info,
    }


def _equal_number(raw, expected):
    num = _number(raw) if isinstance(raw, str) else raw
    return None if num is None else num == Decimal(_num(expected))


def compare_parameters(mission: WaypointMission, audit: dict, geometry: dict,
                       cloud_model_key=None) -> dict:
    """Only compare compatible height frames and one exactly matching route."""
    routes = audit["routes"]
    model, subtype, payload, _ = MODELS[mission.drone_model]
    expected_model = f"0-{model}-{subtype}"
    wpml_model = audit["wpml_model_key"]
    # Aggregate only recognized, documented action names. Never expose free-form
    # actuator contents, unknown enum strings, XML fragments, or action parameters.
    action_type_counts = {}
    start_action_type_counts = {}
    for route in routes:
        for type_name, count in route["action_type_counts"].items():
            action_type_counts[type_name] = action_type_counts.get(type_name, 0) + count
        for type_name, count in route["start_action_type_counts"].items():
            start_action_type_counts[type_name] = start_action_type_counts.get(type_name, 0) + count
    output = {
        "wpml_model_key": wpml_model,
        "wpml_schema_version": audit["wpml_schema_version"],
        "wpml_schema_semantics_verified": audit["wpml_schema_version"] == "1.0.2",
        "cloud_model_key": cloud_model_key,
        "cloud_metadata_wpml_agree": (
            cloud_model_key == wpml_model if cloud_model_key and wpml_model else None
        ),
        "wpml_model_match": wpml_model == expected_model if wpml_model else None,
        "route_count": len(routes),
        "route_point_counts": [len(route["waypoints"]) for route in routes],
        "height_modes": [route["height_mode"] for route in routes],
        "photo_action_count": sum(route["photo_count"] for route in routes),
        "other_action_count": sum(route["other_action_count"] for route in routes),
        "action_type_counts": dict(sorted(action_type_counts.items())),
        "unrecognized_action_count": sum(route["unrecognized_action_count"] for route in routes),
        "start_action_count": sum(route["start_action_count"] for route in routes),
        "start_action_type_counts": dict(sorted(start_action_type_counts.items())),
        "unrecognized_start_action_count": sum(route["unrecognized_start_action_count"] for route in routes),
        "route_start_actions_present": any(route["start_actions_present"] for route in routes),
        "geometry_result": geometry["geometry_result"],
        "parameter_state": "not_comparable",
        "parameter_matches": {},
        "full_content_verified": False,
        "flight_compatibility_verified": False,
    }
    # Don't compare route-specific properties to a partial or multi-folder match.
    if (len(routes) != 1 or geometry.get("geometry_result") != "coordinates_equal"
            or audit["wpml_schema_version"] != "1.0.2"
            or wpml_model != expected_model or not routes[0]["waypoints"]):
        return output
    route = routes[0]
    globals_expected = {
        "flyToWaylineMode": "safely",
        "finishAction": mission.finish_action,
        "exitOnRCLost": "executeLostAction",
        "executeRCLostAction": "goBack",
        "takeOffSecurityHeight": mission.takeoff_security_height_m,
        "globalTransitionalSpeed": mission.speed_mps,
        "globalRTHHeight": mission.rth_height_m,
    }
    comparisons = {}
    for key, expected in globals_expected.items():
        observed = audit["global_fields"][key]
        comparisons[key] = (
            _equal_number(observed, expected) if isinstance(expected, float)
            else None if observed is None else observed == expected
        )
    comparisons["executeHeightMode"] = (
        True if route["height_mode"] == "relativeToStartPoint"
        else None if route["height_mode"] == "unknown" else False
    )
    comparisons["autoFlightSpeed"] = _equal_number(route["speed"], mission.speed_mps)
    # Never compare altitude numerically across different reference planes.
    if comparisons["executeHeightMode"] is True:
        altitudes = [wp["height"] for wp in route["waypoints"]]
        comparisons["waypointHeights"] = (
            None if any(n is None for n in altitudes)
            else all(n == Decimal(_num(mission.altitude_m)) for n in altitudes)
        )
    else:
        comparisons["waypointHeights"] = None
    speeds = [wp["speed"] for wp in route["waypoints"]]
    comparisons["waypointSpeeds"] = (
        None if any(n is None for n in speeds)
        else all(n == Decimal(_num(mission.speed_mps)) for n in speeds)
    )
    expected_actions = [wp.take_photo for wp in waypoints_for_export(mission)]
    if (route["other_action_count"] or route["start_actions_present"]
            or any(wp["action_count"] > 1 or wp["action_structure_unknown"]
                   for wp in route["waypoints"])):
        comparisons["takePhotoPositions"] = None
    else:
        comparisons["takePhotoPositions"] = [
            wp["photo_only"] for wp in route["waypoints"]
        ] == expected_actions

    output["parameter_matches"] = comparisons
    values = list(comparisons.values())
    if any(v is False for v in values):
        output["parameter_state"] = "differences_detected"
    elif any(v is None for v in values):
        output["parameter_state"] = "incomplete_fields"
    else:
        output["parameter_state"] = "supported_fields_equal"
    # Supported fields equal is NOT entire WPML equality, especially camera params.
    return output


async def diagnose_parameters(mission: WaypointMission, *, limit=8,
                              inventory_reader=None, kmz_reader=None,
                              credentials_loader=None):
    """Read up to eight indexed, inventory-verified Pilot 2 KMZs."""
    if type(limit) is not int or not 1 <= limit <= 8:
        raise ValueError("invalid limit")
    reader = inventory_reader or read_waylines
    downloader = kmz_reader or _download_kmz
    loader = credentials_loader or load_credentials
    credentials = loader(credentials_path())
    if credentials is None:
        return {"inventory_state": "not_configured", "results": []}
    inventory = await asyncio.wait_for(reader(credentials), timeout=15)
    if inventory.get("state") != "connected":
        return {"inventory_state": "unavailable", "results": []}
    if (not inventory.get("pagination_complete")
            or inventory.get("workspace_id") != credentials.workspace_id):
        return {"inventory_state": "incomplete_inventory", "results": []}
    result = []
    for idx, route in enumerate(inventory["waylines"][:limit], start=1):
        try:
            content = await asyncio.wait_for(
                downloader(credentials, route["wayline_id"]), timeout=22)
            audit = parse_parameter_audit(content)
            geometry = compare_geometry(mission, route, parse_preview_kmz(content))
            comparison = compare_parameters(
                mission, audit, geometry, route.get("device_model_key"))
            result.append({"index": idx, "state": "connected", **comparison})
        except LocalWaylineError as exc:
            # Never echo upstream diagnostic detail.
            safe = {
                "invalid_archive", "unsupported_geometry",
                "authentication_required", "storage_unavailable",
                "storage_origin_rejected", "invalid_wayline_id",
            }
            result.append({"index": idx, "state": str(exc) if str(exc) in safe else "unavailable"})
        except (httpx.HTTPError, OSError, TimeoutError):
            result.append({"index": idx, "state": "unavailable"})
    return {
        "inventory_state": "connected",
        "reported_total": inventory.get("reported_total"),
        "checked": len(result),
        "results": result,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Read-only Pilot 2 WPML parameter audit. "
                    "No coordinates, IDs, names or credentials in output.")
    parser.add_argument("--mission", help="Existing Studio mission UUID (nicht bei --structure-only)")
    parser.add_argument("--limit", type=int, choices=range(1, 9), default=8)
    parser.add_argument("--structure-only", action="store_true",
                        help="Ausgabe ausschließlich der anonymisierten XML-Struktur")
    args = parser.parse_args()
    if not args.structure_only and not args.mission:
        parser.error("--mission erforderlich ohne --structure-only")
    try:
        if args.structure_only:
            report = asyncio.run(diagnose_structure(limit=args.limit))
        else:
            mission = read_local_mission(args.mission)
            report = asyncio.run(diagnose_parameters(mission, limit=args.limit))
    except (WorkspaceError, ValueError, KeyError, TypeError, LocalWaylineError):
        report = {"inventory_state": "invalid_or_unavailable_mission", "results": []}
    except (httpx.HTTPError, OSError, TimeoutError):
        report = {"inventory_state": "unavailable", "results": []}
    except KeyboardInterrupt:
        return 130
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["inventory_state"] == "connected" and all(
        r["state"] == "connected" for r in report["results"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
