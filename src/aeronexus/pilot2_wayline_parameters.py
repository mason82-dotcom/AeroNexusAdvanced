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
FIELDS = (
    "flyToWaylineMode", "finishAction", "exitOnRCLost",
    "executeRCLostAction", "takeOffSecurityHeight",
    "globalTransitionalSpeed", "globalRTHHeight",
)
MODES = {"relativeToStartPoint", "WGS84", "realTimeFollowSurface"}
_MODEL_PART = re.compile(r"[0-9]{1,5}\Z")


def _child_text(parent, tag):
    if parent is None:
        return None
    elems = parent.findall(W + tag)
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


def _model_key(node):
    a = _child_text(node, "droneEnumValue")
    b = _child_text(node, "droneSubEnumValue")
    return f"0-{a}-{b}" if a and b and _MODEL_PART.fullmatch(a) and _MODEL_PART.fullmatch(b) else None


def _read_xml(kmz: bytes):
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
    root = _xml_root(data)
    if root.tag != K + "kml":
        raise LocalWaylineError("unsupported_geometry")
    doc = root.find(K + "Document")
    if doc is None:
        raise LocalWaylineError("unsupported_geometry")
    return doc


def parse_parameter_audit(kmz: bytes) -> dict:
    """Bounded, allowlisted, position-free WPML audit over actual executable Folders."""
    doc = _read_xml(kmz)
    config = doc.find(W + "missionConfig")
    folders = doc.findall(K + "Folder")
    if config is None or not 1 <= len(folders) <= MAX_FEATURES:
        raise LocalWaylineError("unsupported_geometry")

    drone = config.find(W + "droneInfo")
    payload = config.find(W + "payloadInfo")
    global_fields = {field: _child_text(config, field) for field in FIELDS}
    route_info = []
    total = 0
    for folder in folders:
        places = folder.findall(K + "Placemark")
        total += len(places)
        if total > MAX_ELEMENTS:
            raise LocalWaylineError("invalid_archive")
        waypoints, photo_count, other_action_count = [], 0, 0
        for place in places:
            point = place.find(K + "Point")
            coords = point.find(K + "coordinates") if point is not None else None
            if coords is None or coords.text is None:
                raise LocalWaylineError("unsupported_geometry")
            # Validate values, but coordinates are NEVER returned in the audit.
            _coordinate(coords.text)
            action_nodes = place.findall(".//" + W + "action")
            actions = [
                item.text.strip() if item.text else None
                for item in place.findall(".//" + W + "actionActuatorFunc")
            ]
            action_structure_unknown = (
                len(action_nodes) != len(actions)
                or (bool(place.findall(".//" + W + "actionGroup")) and not action_nodes)
            )
            photo_count += actions.count("takePhoto")
            other_action_count += len(actions) - actions.count("takePhoto")
            waypoints.append({
                "height": _number(_child_text(place, "executeHeight")),
                "speed": _number(_child_text(place, "waypointSpeed")),
                "photo_only": actions == ["takePhoto"],
                "no_actions": len(actions) == 0,
                "action_count": len(actions),
                "action_structure_unknown": action_structure_unknown,
            })
        mode = _child_text(folder, "executeHeightMode")
        route_info.append({
            "height_mode": mode if mode in MODES else "unknown",
            "speed": _number(_child_text(folder, "autoFlightSpeed")),
            "waypoints": waypoints,
            "photo_count": photo_count,
            "other_action_count": other_action_count,
            "start_actions_present": folder.find(W + "startActionGroup") is not None,
        })
    return {
        "wpml_model_key": _model_key(drone),
        "wpml_payload_key": _child_text(payload, "payloadEnumValue"),
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
    output = {
        "wpml_model_key": wpml_model,
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
        "route_start_actions_present": any(route["start_actions_present"] for route in routes),
        "geometry_result": geometry["geometry_result"],
        "parameter_state": "not_comparable",
        "parameter_matches": {},
        "full_content_verified": False,
        "flight_compatibility_verified": False,
    }
    # Don't compare route-specific properties to a partial or multi-folder match.
    if (len(routes) != 1 or geometry.get("geometry_result") != "coordinates_equal"
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
    parser.add_argument("--mission", required=True, help="Existing Studio mission UUID")
    parser.add_argument("--limit", type=int, choices=range(1, 9), default=8)
    args = parser.parse_args()
    try:
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
