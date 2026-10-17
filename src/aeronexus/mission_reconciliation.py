"""Read-only metadata comparison; never a synchronization or flight command.

Cloud route names are hints, not identifiers. No file checksum/geometry or
stable cross-system mission reference is available in the existing catalog.
"""
import unicodedata

from .flighthub_catalog import MAX_ITEMS, TASK_WINDOW_DAYS
from .wpml_export import MODELS


def _name(value: str | None) -> str:
    return " ".join(unicodedata.normalize("NFC", value or "").casefold().split())


def compare_missions(missions: list[dict], catalog: dict, updated_at: str | None) -> dict:
    """Compare only already authorized local/cache data, without network IO.

    Lists may be capped by the upstream reader. Absence is not evidence of
    deletion. Each source remains explicitly named and project-scoped.
    """
    projects, routes, tasks = [], [], []
    for (provider, project_id), cached in catalog.items():
        source = {"provider": provider.value, "project_id": project_id}
        waylines = cached.get("waylines")
        flight_tasks = cached.get("tasks")
        projects.append({**source,
                         "waylines_readable": waylines is not None,
                         "tasks_readable": flight_tasks is not None,
                         "waylines_at_limit": len(waylines or []) >= MAX_ITEMS,
                         "tasks_at_limit": len(flight_tasks or []) >= MAX_ITEMS})
        for route in waylines or []:
            # Explicit output allowlist: no signed URLs or upstream raw values.
            routes.append({**source, "wayline_id": route.get("id"),
                           "name": route.get("name"),
                           "template_types": route.get("template_types", []),
                           "device_model_key": route.get("device_model_key"),
                           "updated_at": route.get("updated_at"),
                           "size_bytes": route.get("size_bytes")})
        for task in flight_tasks or []:
            tasks.append({**source, "task_uuid": task.get("uuid"),
                          "name": task.get("name"), "status": task.get("status"),
                          "wayline_link": "unavailable"})
    rows = []
    for mission in missions:
        aircraft, subtype, _, _ = MODELS[mission["drone_model"]]
        model_key = f"0-{aircraft}-{subtype}"
        candidates = []
        for route in routes:
            if _name(mission["name"]) and _name(mission["name"]) == _name(route["name"]):
                candidate_model = route["device_model_key"]
                candidates.append({**route,
                                   "model_match": candidate_model == model_key if candidate_model else None,
                                   "content_match": None, "verification": "name_only"})
        rows.append({"local_id": mission["id"], "name": mission["name"],
                     "drone_model": mission["drone_model"],
                     "waypoints": mission.get("waypoints"),
                     "device_model_key": model_key,
                     "status": "unverified_candidates" if candidates else "no_candidate_in_cache",
                     "candidate_count": len(candidates), "candidates": candidates[:10]})
    return {"catalog_updated_at": updated_at, "projects": projects,
            "missions": rows, "waylines": routes, "flight_tasks": tasks,
            "coverage": {"source": "cached_flighthub_public",
                         "cloud_cache_available": bool(catalog),
                         "full_inventory_verified": False,
                         "pilot2_local_cloud": "not_connected",
                         "task_window_days": TASK_WINDOW_DAYS,
                         "max_items_per_project_collection": MAX_ITEMS,
                         "max_candidates_per_mission": 10,
                         "route_content_verified": False}}
