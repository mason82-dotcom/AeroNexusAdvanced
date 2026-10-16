"""FlightHub 2 Public Cloud project library: waylines, map models, flight
tasks and task tracks, read-only.

Endpoints (OpenAPI V2.0 reference, same paths in v0.1):
  GET /wayline                     wayline list of the project
  GET /model                       2D/3D map models of the project
  GET /flight-task/list            flight tasks in a time window
  GET /flight-task/{uuid}/track    flown trajectory of a task
  GET /flight-task/{uuid}/media    media filenames and metadata (NO download URLs)
  GET /system_status               FlightHub 2 system status

Feature set and the track-to-GeoJSON shape follow alecad/dji-flighthub2-cli
(Apache-2.0: ``fh2 wayline list``, ``fh2 model list``, ``fh2 task list``,
``fh2 task track --geojson``). Download URLs and other signed links are never
stored or forwarded.
"""
from collections.abc import Mapping
import time
from uuid import UUID

from .providers import ProviderConfig, ProviderKind
from .read_only_transport import ReadOnlyTransport


class CatalogError(ValueError):
    pass


MAX_ITEMS = 200
MAX_TRACK_POINTS = 20000
TASK_WINDOW_DAYS = 30
TEMPLATE_TYPES = ("waypoint", "mapping_2d", "mapping_3d", "mapping_strip",
                  "facade", "solid", "mapping_gobject")
TASK_STATUSES = ("waiting", "starting_failure", "executing", "paused", "terminated",
                 "success", "suspended", "timeout", "partially_done", "preparing")


def _uuid(value) -> str:
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise CatalogError("Invalid UUID") from exc


def _rows(payload) -> list:
    if not isinstance(payload, Mapping) or payload.get("code") != 0:
        raise CatalogError("Unsuccessful FlightHub response")
    data = payload.get("data")
    rows = data.get("list", ...) if isinstance(data, Mapping) else ...
    if rows is None:
        return []  # empty collections arrive as {"list": null}
    if not isinstance(rows, list):
        raise CatalogError("Invalid FlightHub list")
    if len(rows) > MAX_ITEMS:
        rows = rows[:MAX_ITEMS]
    return [row for row in rows if isinstance(row, Mapping)]


def _text(value, limit: int = 200) -> str | None:
    return value.strip()[:limit] if isinstance(value, str) and value.strip() else None


def _int(value) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _number(value) -> float | None:
    if type(value) in (int, float) and value == value and abs(value) != float("inf"):
        return value
    return None


def normalize_waylines(payload) -> tuple[dict, ...]:
    result = []
    for row in _rows(payload):
        templates = row.get("template_types") or []
        payloads = row.get("payload_information") or []
        result.append({
            "id": _text(row.get("id"), 64),
            "name": _text(row.get("name")),
            "template_types": [t for t in templates if t in TEMPLATE_TYPES]
            if isinstance(templates, list) else [],
            "device_model_key": _text(row.get("device_model_key"), 32),
            "lenses": sorted({p.get("lens_type") for p in payloads
                              if isinstance(p, Mapping) and p.get("lens_type") in ("wide", "zoom", "ir")})
            if isinstance(payloads, list) else [],
            "updated_at": _int(row.get("update_time")),
            "size_bytes": _int(row.get("size")),
        })
    return tuple(result)


def normalize_models(payload) -> tuple[dict, ...]:
    return tuple({
        "id": _int(row.get("id")),
        "name": _text(row.get("name")),
        "file_type": row.get("file_type") if row.get("file_type") in ("model_2d", "model_3d") else None,
        "show_on_map": row.get("show_on_map") is True,
        "size_bytes": _int(row.get("size")),
        "updated_at_ms": _int(row.get("update_at")),
    } for row in _rows(payload))


def normalize_tasks(payload) -> tuple[dict, ...]:
    result = []
    for row in _rows(payload):
        try:
            task_uuid = _uuid(row.get("uuid"))
        except CatalogError:
            continue
        status = row.get("status")
        result.append({
            "uuid": task_uuid,
            "name": _text(row.get("name")),
            "task_type": row.get("task_type") if row.get("task_type") in (
                "immediate", "timed", "recurring", "continuous") else None,
            "status": status if status in TASK_STATUSES else ("unknown" if status else None),
            "begin_at": _text(row.get("begin_at"), 40),
            "run_at": _text(row.get("run_at"), 40),
            "completed_at": _text(row.get("completed_at"), 40),
            "current_waypoint_index": _int(row.get("current_waypoint_index")),
            "total_waypoints": _int(row.get("total_waypoints")),
            "media_upload_status": _text(row.get("media_upload_status"), 32),
            "exceptions": len(row.get("exceptions") or []) if isinstance(row.get("exceptions"), list) else 0,
        })
    return tuple(result)


def normalize_task_media(payload) -> tuple[dict, ...]:
    """Safe media metadata from a known FlightHub task, NEVER signed URLs.

    The CLI reference tolerates data as a list or data.list; both occur in
    DJI endpoints. Everything else fails closed rather than forwarding a raw
    upstream object containing temporary storage credentials.
    """
    if not isinstance(payload, Mapping) or payload.get("code") != 0:
        raise CatalogError("Unsuccessful FlightHub response")
    data = payload.get("data")
    if isinstance(data, list):
        rows = data
    elif isinstance(data, Mapping):
        rows = data.get("list")
    else:
        rows = None
    if rows is None:
        rows = []
    if not isinstance(rows, list):
        raise CatalogError("Invalid FlightHub media list")
    result = []
    for media in rows[:MAX_ITEMS]:
        if not isinstance(media, Mapping):
            continue
        # Only explicitly named, non-executable file types. No preview_url,
        # original_url, storage object keys, file paths or arbitrary fields.
        mime = _text(media.get("file_type"), 40)
        suffix = _text(media.get("suffix"), 12)
        result.append({
            "id": _text(media.get("uuid"), 64),
            "name": _text(media.get("name"), 200),
            "file_type": mime,
            "suffix": suffix,
            "size_bytes": _int(media.get("size")),
            "created_at": _text(media.get("create_at"), 40),
            "updated_at": _text(media.get("update_at"), 40),
        })
    return tuple(result)


def track_geojson(payload) -> dict:
    """GeoJSON Feature (LineString lon/lat/height), like fh2 task track --geojson."""
    if not isinstance(payload, Mapping) or payload.get("code") != 0:
        raise CatalogError("Unsuccessful FlightHub response")
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise CatalogError("Missing track data")
    track = data.get("track") if isinstance(data.get("track"), Mapping) else {}
    points = track.get("points") or []
    if not isinstance(points, list):
        raise CatalogError("Invalid track points")
    coordinates = []
    for point in points[:MAX_TRACK_POINTS]:
        if not isinstance(point, Mapping):
            continue
        lat, lon = _number(point.get("latitude")), _number(point.get("longitude"))
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        if lat == 0 and lon == 0:
            continue  # DJI "no position"
        height = _number(point.get("height"))
        coordinates.append([lon, lat] + ([height] if height is not None else []))
    return {
        "type": "Feature",
        "properties": {
            "name": _text(data.get("name")),
            "flight_distance": _number(track.get("flight_distance")),
            "flight_duration": _number(track.get("flight_duration")),
            "points": len(coordinates),
        },
        "geometry": {"type": "LineString", "coordinates": coordinates},
    }


def _require_public(config: ProviderConfig) -> None:
    if config.kind != ProviderKind.PUBLIC_V2:
        raise CatalogError("Public Cloud provider required")


async def _get(config: ProviderConfig, suffix: str, project_uuid: str, params=None) -> dict:
    path = config.path(suffix)
    return await ReadOnlyTransport(config, frozenset({path})).get(
        path, params, project_uuid=project_uuid)


async def read_catalog(config: ProviderConfig, project_uuid: str, *, now: float | None = None) -> dict:
    """One project's library; each list is independent (None = could not be read)."""
    _require_public(config)
    project_uuid = _uuid(project_uuid)
    now = int(time.time() if now is None else now)
    result: dict = {"waylines": None, "models": None, "tasks": None,
                    "task_window_days": TASK_WINDOW_DAYS}
    readers = (
        ("waylines", "/wayline", None, normalize_waylines),
        ("models", "/model", None, normalize_models),
        ("tasks", "/flight-task/list",
         {"begin_at": now - TASK_WINDOW_DAYS * 86400, "end_at": now}, normalize_tasks),
    )
    for key, suffix, params, normalize in readers:
        try:
            result[key] = list(normalize(await _get(config, suffix, project_uuid, params)))
        except (ValueError, RuntimeError):
            result[key] = None  # best effort; other lists still show
    return result


async def read_system_status(config: ProviderConfig, project_uuid: str) -> bool:
    _require_public(config)
    await _get(config, "/system_status", _uuid(project_uuid))
    return True


async def read_task_track(config: ProviderConfig, project_uuid: str, task_uuid: str) -> dict:
    _require_public(config)
    return track_geojson(await _get(config, f"/flight-task/{_uuid(task_uuid)}/track",
                                    _uuid(project_uuid)))


async def read_task_media(config: ProviderConfig, project_uuid: str, task_uuid: str) -> tuple[dict, ...]:
    """Read metadata for an already-authorized and catalog-scoped task only."""
    _require_public(config)
    task = _uuid(task_uuid)
    return normalize_task_media(
        await _get(config, f"/flight-task/{task}/media", _uuid(project_uuid)))
