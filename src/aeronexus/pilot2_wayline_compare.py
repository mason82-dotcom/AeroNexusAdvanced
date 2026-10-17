"""Read-only geometry-only comparison of a local Studio mission with a Pilot 2 KMZ.

This is intentionally NOT a WPML semantic validation. Equal coordinates do
not prove equal camera actions, speeds, heights, routes or flight safety.
Only selected, inventory-verified waylines are downloaded; no POST or MQTT.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
from math import isfinite
from uuid import UUID

import httpx

from .local_waylines import LocalWaylineError, credentials_path, load_credentials, read_waylines
from .pilot2_wayline_preview import read_preview, MAX_ELEMENTS, MAX_FEATURES
from .studio_workspace import WorkspaceError, _read_json, safe_id
from .wpml_export import MODELS, WaypointMission, _num, waypoints_for_export


def _private_directory(path: Path) -> None:
    if not path.is_dir() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise WorkspaceError("workspace_unavailable")


def read_local_mission(mission_id: str) -> WaypointMission:
    """Read an existing private mission without constructing/creating a Workspace."""
    item_id = safe_id(mission_id)
    root = Path(os.environ.get(
        "AERONEXUS_WORKSPACE_DIR", "~/.local/share/aeronexusadvanced")).expanduser()
    _private_directory(root)
    missions = root / "missions"
    _private_directory(missions)
    path = missions / (item_id + ".json")
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise WorkspaceError("workspace_unavailable")
    record = _read_json(path)
    if record.get("id") != item_id:
        raise WorkspaceError("workspace_unavailable")
    return WaypointMission.model_validate(record["mission"])


def _expected(mission: WaypointMission) -> list[tuple[float, float]]:
    # Export rounds coordinates to seven decimal places. Compare the
    # transmitted representation, not unconstrained user-input precision.
    return [(float(_num(w.longitude)), float(_num(w.latitude)))
            for w in waypoints_for_export(mission)]


def _geometry_segments(preview: dict):
    if not isinstance(preview, dict) or preview.get("source") != "waylines.wpml":
        return None
    features = preview.get("features")
    if not isinstance(features, list) or not 1 <= len(features) <= MAX_FEATURES:
        return None
    segments, count = [], 0
    for feature in features:
        if not isinstance(feature, dict) or not isinstance(feature.get("geometry"), dict):
            return None
        geom = feature["geometry"]
        kind = geom.get("type")
        values = geom.get("coordinates")
        if kind == "Point":
            values = [values]
        elif kind != "LineString":
            return None
        if not isinstance(values, list) or not values:
            return None
        segment = []
        for point in values:
            if (not isinstance(point, list) or len(point) != 2
                    or any(type(v) not in (float, int) or not isfinite(v) for v in point)
                    or not -180 <= point[0] <= 180 or not -90 <= point[1] <= 90):
                return None
            segment.append((float(point[0]), float(point[1])))
        segments.append(segment)
        count += len(segment)
        if count > MAX_ELEMENTS:
            return None
    return segments


def compare_geometry(mission: WaypointMission, cloud: dict, preview: dict) -> dict:
    """Report limited coordinate evidence; never report complete mission equality."""
    model, subtype, _, _ = MODELS[mission.drone_model]
    expected_model = f"0-{model}-{subtype}"
    cloud_model = cloud.get("device_model_key")
    model_match = None if cloud_model is None else cloud_model == expected_model
    expected = _expected(mission)
    segments = _geometry_segments(preview)
    output = {
        "geometry_result": "unsupported_geometry",
        "model_match": model_match,
        "studio_point_count": len(expected),
        "cloud_point_count": sum(map(len, segments)) if segments is not None else None,
        "cloud_feature_count": len(segments) if segments is not None else None,
        "full_content_verified": False,
        "flight_compatibility_verified": False,
    }
    if not expected or segments is None:
        return output
    if len(segments) == 1 and segments[0] == expected:
        result = "coordinates_equal"
    elif len(segments) > 1 and any(seg == expected for seg in segments):
        result = "matching_segment_with_extras"
    elif len(segments) > 1 and [p for seg in segments for p in seg] == expected:
        result = "multipart_order_matches"
    else:
        result = "coordinates_different"
    if model_match is False and result == "coordinates_equal":
        result = "model_conflict"
    output["geometry_result"] = result
    return output


async def check_mission(mission: WaypointMission, wayline_id: str, *,
                        inventory_reader=read_waylines, preview_reader=read_preview,
                        load=load_credentials) -> dict:
    """Check only an explicit UUID against a full local Pilot 2 inventory."""
    wayline_id = str(UUID(wayline_id))
    credentials = load(credentials_path())
    if credentials is None:
        return {"state": "not_configured"}
    inventory = await asyncio.wait_for(inventory_reader(credentials), timeout=15)
    if inventory.get("state") != "connected":
        return {"state": "upstream_error"}
    if not inventory.get("pagination_complete"):
        return {"state": "incomplete_inventory"}
    if inventory.get("workspace_id") != credentials.workspace_id:
        return {"state": "invalid_response"}
    matches = [r for r in inventory.get("waylines", [])
               if r.get("wayline_id") == wayline_id]
    if len(matches) != 1:
        return {"state": "wayline_not_found"}
    preview = await asyncio.wait_for(
        preview_reader(credentials, wayline_id), timeout=22)
    return {"state": "connected", **compare_geometry(mission, matches[0], preview)}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare private Studio/Pilot-2 wayline coordinates, GET-only. "
                    "No position, UUID, name, credential or signed URL is printed.")
    parser.add_argument("--mission", required=True, help="Existing local Studio mission UUID")
    parser.add_argument("--wayline", required=True, help="Exact Pilot 2 Cloud wayline UUID")
    args = parser.parse_args()
    try:
        # Validate IDs before any local/cloud file access; never echo raw IDs.
        mission_id, wayline_id = str(UUID(args.mission)), str(UUID(args.wayline))
        mission = read_local_mission(mission_id)
        result = asyncio.run(check_mission(mission, wayline_id))
    except (ValueError, TypeError, KeyError, WorkspaceError) as exc:
        status = str(exc) if isinstance(exc, LocalWaylineError) else "invalid_or_unavailable_mission"
        allowed = {"configuration_error", "authentication_required", "inventory_changed",
                   "invalid_response", "business_error", "storage_unavailable",
                   "storage_origin_rejected", "invalid_archive", "unsupported_geometry",
                   "upstream_error", "wayline_not_found"}
        result = {"state": status if status in allowed else "invalid_or_unavailable_mission"}
    except (httpx.HTTPError, OSError, TimeoutError):
        result = {"state": "unavailable"}
    except KeyboardInterrupt:
        return 130
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("state") == "connected" else 1


if __name__ == "__main__":
    raise SystemExit(main())
