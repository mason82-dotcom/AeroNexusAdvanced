"""Read-only API gateway with an authenticated fleet-status view.

DJI flight operations are not exposed. Detailed telemetry is inaccessible
unless an independent dashboard bearer token is configured.
"""
import asyncio
import httpx
from io import BytesIO
from urllib.parse import unquote
from contextlib import asynccontextmanager
import os
import re
import sqlite3
import sys
import time
import threading
from typing import Annotated, Literal
from enum import Enum
from secrets import compare_digest

from fastapi import FastAPI, Header, HTTPException, Query, Response, Request, WebSocket
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from datetime import datetime

from .cloud_api_mqtt import CloudMqttFeed, CloudOsdIngest, MqttSettings
from .dji_media_index import MediaIndexError, browse_media, index_summary
from .dji_media_page import render_dji_media_page
from .cloud_api2_bridge import CloudApi2Bridge, CloudApi2Settings
from .flighthub_catalog import read_task_track, read_task_media
from .flighthub_poller import FlightHubFleetRefresher, FlightHubPollSettings
from .providers import ProviderKind
from .status_page import render_page
from .studio_page import render_studio
from .operations_page import render_operations
from .studio_workspace import Workspace, WorkspaceError, MAX_MEDIA_BYTES, MEDIA_TYPES
from .minio_media_index import (DjiMediaChanged, DjiMediaIndex, DjiMediaError, MinioMediaSettings,
                                minio_client, BROWSER_PREVIEW_MIMES,
                                MAX_BROWSER_PREVIEW_BYTES)
from .geo_planning import GeoObject, SurveyPlanRequest, generate_survey_preview
from .thermal import ThermalChanged, ThermalError, ThermalNotFound, ThermalService
from .thermal_page import render_thermal_page
from .multispectral import (LAYERS, MultispectralBusy, MultispectralError, MultispectralNotFound,
                            MultispectralService)
from .multispectral_page import render_multispectral_page
from .thermal_flights import ThermalFlights, ThermalJobRunning
from .media_sync import read_status as read_media_sync_status
from .photo_catalog import PhotoCatalog
from .cloud_stack import CloudStackHealth, fleet_view, overall as cloud_overall
from .livestream import LiveError, LiveNotFound, LiveStreams, LiveUnavailable
from .metashape_bridge import (MetashapeExportBusy, MetashapeExportError, MetashapePackageNotFound,
                               list_packages, package_path, prepare_package, remove_package)
from .raster_results import (RasterResults, RasterError, RasterUnavailable,
                             RasterNotFound, RasterChanged, RasterBusy, _libraries)
from .results_page import render_results_page
from .multispectral_report import build_report, report_csv
from .pv_inspection import PvConditions, PvInspectionError, PvThresholds, Region
from .thermal_sdk import MeasureParams, ThermalSdkBusy, ThermalSdkError, ThermalSdkUnavailable
from .terrain_preview import TerrainGrid, TerrainUnavailable, terrain_overview, terrain_stl, geotiff_preview
from .studio_events import serve_studio_events
from .lan_access import lan_host, lan_mode_enabled, require_lan
from .wpml_export import WaypointMission, export_kmz, import_kmz
from .mission_reconciliation import compare_missions
from .local_waylines import LocalWaylineReader, load_credentials, credentials_path
from .pilot2_wayline_preview import read_preview
from .pilot2_readonly import Pilot2ReadOnlyReader
from .pilot2_action_summary import Pilot2ActionSummaryReader
from .local_waylines import Credentials, LocalWaylineError
from .local_session import LocalSessionHandoff, handoff_origin
from .mission_csv import MAX_CSV_BYTES, MissionCsvError, preview_csv
from .status_polling import ReadOnlyStatusPoller
from .status_runtime import StatusRuntime, StatusSettings
from .hms_history import HmsHistory, default_history_path


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start read-only data sources only when explicitly enabled."""
    settings = MqttSettings.from_env()
    poll_settings = FlightHubPollSettings.from_env()
    api2_settings = CloudApi2Settings.from_env()
    app.state.cloud_api2_bridge = CloudApi2Bridge(api2_settings) if api2_settings else None
    app.state.local_waylines = LocalWaylineReader()
    app.state.local_pilot_reader = Pilot2ReadOnlyReader()
    app.state.pilot2_action_summary = Pilot2ActionSummaryReader(app.state.local_waylines)
    app.state.local_session_handoff = LocalSessionHandoff()
    app.state.provider_configured = {
        Provider.public_v2: poll_settings is not None and poll_settings.config.kind == ProviderKind.PUBLIC_V2,
        Provider.onprem_v2: poll_settings is not None and poll_settings.config.kind == ProviderKind.ONPREM_V2,
        Provider.cloud_api: settings is not None or api2_settings is not None,
    }
    feed = None
    poll_task = None
    app.state.flighthub = None
    app.state.track_cache = {}
    app.state.task_media_cache = {}
    stop_polling = asyncio.Event()
    if settings is not None:
        runtime = app.state.status_runtime
        if settings.include_hms:
            runtime.hms_history = HmsHistory(default_history_path())
        ingest = CloudOsdIngest(runtime, settings.project_id, settings.max_devices)
        feed = CloudMqttFeed(settings, ingest)
        runtime.live_feed = feed.status
        feed.start(asyncio.get_running_loop())
    if poll_settings is not None:
        runtime = app.state.status_runtime
        refresher = FlightHubFleetRefresher(runtime, poll_settings)
        app.state.flighthub = refresher
        poller = ReadOnlyStatusPoller(
            runtime, refresher, interval_seconds=poll_settings.interval_seconds)
        poll_task = asyncio.create_task(poller.run(stop_polling))
    app.state.cloud_feed = feed
    try:
        yield
    finally:
        if feed is not None:
            feed.stop()
        if poll_task is not None:
            stop_polling.set()
            await poll_task


app = FastAPI(title="AeroNexusAdvanced", version="0.1.0", lifespan=lifespan)
app.state.cloud_api2_bridge = None
try:  # Starlette >= 0.46 can skip media and event streams; older versions are left uncompressed
    from starlette.middleware.gzip import DEFAULT_EXCLUDED_CONTENT_TYPES as _GZIP_SKIP
except ImportError:
    _GZIP_SKIP = None
if _GZIP_SKIP is not None:
    # JSON maps and pages compress about tenfold; originals and downloads stay byte-identical.
    app.add_middleware(GZipMiddleware, minimum_size=2048, compresslevel=5,
                       exclude_content_types=_GZIP_SKIP + (
                           "image/*", "application/octet-stream",
                           "application/vnd.google-earth.kmz", "model/stl"))
app.state.task_media_cache = {}
app.state.studio_event_clients = 0
app.state.status_runtime = StatusRuntime(
    settings=StatusSettings(
        stale_after_seconds=int(os.environ.get("AERONEXUS_STATUS_STALE_AFTER_SECONDS", "90")),
        refresh_every_seconds=int(os.environ.get("AERONEXUS_STATUS_REFRESH_SECONDS", "30")),
    ),
)


class Provider(str, Enum):
    public_v2 = "flighthub-public-v2"
    onprem_v2 = "flighthub-onprem-v2"
    cloud_api = "dji-cloud-api"


class ProviderStatus(BaseModel):
    provider: Provider
    configured: bool = False
    flight_commands_enabled: bool = False


def _no_cache(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"


def _require_dashboard_token(authorization: str | None) -> None:
    """Fail closed: do not reuse the DJI API credential for dashboard reads."""
    configured = os.environ.get("AERONEXUS_STATUS_TOKEN", "")
    if (not 32 <= len(configured) <= 512 or not configured.isascii()
            or any(char.isspace() for char in configured)):
        raise HTTPException(status_code=503, detail="Status detail authentication is not configured")
    if (not isinstance(authorization, str) or len(authorization) > 512
            or not authorization.startswith("Bearer ")
            or not compare_digest(authorization[7:], configured)):
        raise HTTPException(
            status_code=401, detail="Invalid status access credential",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _require_viewer_access(request: Request, authorization: str | None) -> None:
    """Optional token-free LAN mode; existing bearer mode stays the default."""
    if lan_mode_enabled():
        require_lan(request)
    else:
        _require_dashboard_token(authorization)


@app.get("/", include_in_schema=False)
def dashboard_home() -> RedirectResponse:
    """Relative redirect keeps the current HTTPS origin, IP and port."""
    return RedirectResponse(
        url="/status", status_code=307,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "aeronexusadvanced"}


@app.get("/api/v1/providers", response_model=list[ProviderStatus])
def providers() -> list[ProviderStatus]:
    return [provider_status(provider) for provider in Provider]


@app.get("/api/v1/providers/{provider}/status", response_model=ProviderStatus)
def provider_status(provider: Provider) -> ProviderStatus:
    configured = getattr(app.state, "provider_configured", {}).get(provider, False)
    return ProviderStatus(provider=provider, configured=configured)


@app.get("/api/v1/status/summary")
async def status_summary(response: Response) -> dict:
    """Only anonymous aggregate counts; never device IDs or GPS positions."""
    _no_cache(response)
    return app.state.status_runtime.summary()


@app.get("/api/v1/cloud/stack")
async def cloud_stack_status(request: Request, response: Response,
                             authorization: str | None = Header(default=None)) -> dict:
    """Reachability of the local DJI Cloud API stack and its connected devices."""
    _require_viewer_access(request, authorization)
    _no_cache(response)
    health = getattr(app.state, "cloud_stack_health", None)
    if health is None:
        try:
            health = app.state.cloud_stack_health = CloudStackHealth()
        except ValueError as exc:
            raise HTTPException(status_code=503, detail="Cloud stack host not configured") from exc
    services = await health.services()
    runtime = app.state.status_runtime
    fleet = fleet_view(runtime.device_views(), runtime.summary().get("live_feed"))
    return {"overall": cloud_overall(services, fleet), "services": services, "fleet": fleet}


@app.get("/api/v1/status/devices")
async def status_devices(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    provider: ProviderKind | None = None,
    project_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Authenticated details, bounded pagination, no external DJI fetch."""
    _no_cache(response)
    _require_viewer_access(request, authorization)
    devices = app.state.status_runtime.device_views(provider, project_id)
    return {"total": len(devices), "offset": offset, "limit": limit,
            "devices": list(devices[offset:offset + limit])}


@app.get("/api/v1/status/hms-history")
async def status_hms_history(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    device_id: str | None = Query(default=None, min_length=1, max_length=80),
    project_id: str | None = Query(default=None, min_length=1, max_length=128),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Protected, bounded local history of HMS transitions (not raw DJI messages)."""
    _no_cache(response)
    _require_viewer_access(request, authorization)
    return app.state.status_runtime.hms_history.list_events(
        provider=ProviderKind.CLOUD_API.value, project_id=project_id,
        device_id=device_id, limit=limit, offset=offset
    )


@app.get("/api/v1/dji/media/summary")
def dji_media_summary(request: Request, response: Response,
                      authorization: str | None = Header(default=None)) -> dict:
    """Locally indexed MinIO object-list metadata; no MinIO network access."""
    _no_cache(response)
    _require_viewer_access(request, authorization)
    try:
        return index_summary()
    except (OSError, sqlite3.Error, WorkspaceError, MediaIndexError) as exc:
        raise HTTPException(status_code=503, detail="DJI media index unavailable") from exc


@app.get("/api/v1/media/sync")
def media_sync_status(request: Request, response: Response,
                      authorization: str | None = Header(default=None)) -> dict:
    """State of the automatic catalogue sync after Pilot 2 uploads (read-only)."""
    workspace = _studio_workspace(request, authorization)
    _no_cache(response)
    return read_media_sync_status(workspace.root)


@app.get("/api/v1/dji/media")
def dji_media_list(request: Request, response: Response,
                   authorization: str | None = Header(default=None),
                   kind: str | None = None,
                   q: str = Query(default="", max_length=200),
                   limit: int = Query(default=50, ge=1, le=100),
                   offset: int = Query(default=0, ge=0, le=1000000)) -> dict:
    """Paginated metadata only: never disclose S3 paths or signed URLs."""
    _no_cache(response)
    _require_viewer_access(request, authorization)
    if kind is not None and kind not in ("image", "raw", "video", "audio", "sidecar"):
        raise HTTPException(status_code=422, detail="Unsupported media category")
    try:
        return browse_media(kind=kind, query=q, limit=limit, offset=offset)
    except (OSError, sqlite3.Error, WorkspaceError, MediaIndexError) as exc:
        raise HTTPException(status_code=503, detail="DJI media index unavailable") from exc



_PHOTO_FILTER = re.compile(r"[A-Za-z0-9_]{1,32}\Z")
_PHOTO_ID = re.compile(r"[0-9a-f]{64}\Z")


def _photo_catalog(request: Request, authorization: str | None) -> PhotoCatalog:
    workspace = _studio_workspace(request, authorization)
    return PhotoCatalog(DjiMediaIndex(workspace.root))


def _photo_filters(model: str | None, camera: str | None) -> tuple[str | None, str | None]:
    for value in (model, camera):
        if value is not None and not _PHOTO_FILTER.fullmatch(value):
            raise HTTPException(status_code=422, detail="Invalid model or camera filter")
    return model or None, camera or None


@app.get("/api/v1/photos/summary")
def photo_summary(request: Request, response: Response,
                  authorization: str | None = Header(default=None)) -> dict:
    """Aircraft models and cameras of all indexed DJI JPEGs (from their own metadata)."""
    catalog = _photo_catalog(request, authorization)
    _no_cache(response)
    try:
        return catalog.summary()
    except (OSError, sqlite3.Error, DjiMediaError) as exc:
        raise HTTPException(status_code=503, detail="Photo catalogue unavailable") from exc


@app.get("/api/v1/photos/flights")
def photo_flights(request: Request, response: Response,
                  model: str | None = Query(default=None, max_length=32),
                  camera: str | None = Query(default=None, max_length=32),
                  authorization: str | None = Header(default=None)) -> dict:
    catalog = _photo_catalog(request, authorization)
    model, camera = _photo_filters(model, camera)
    _no_cache(response)
    try:
        return {"flights": catalog.flights(model=model, camera=camera)}
    except (OSError, sqlite3.Error, DjiMediaError) as exc:
        raise HTTPException(status_code=503, detail="Photo catalogue unavailable") from exc


@app.get("/api/v1/photos")
def photo_list(request: Request, response: Response,
               model: str | None = Query(default=None, max_length=32),
               camera: str | None = Query(default=None, max_length=32),
               flight: str | None = Query(default=None, max_length=64),
               limit: int = Query(default=50, ge=1, le=200),
               offset: int = Query(default=0, ge=0, le=1_000_000),
               authorization: str | None = Header(default=None)) -> dict:
    catalog = _photo_catalog(request, authorization)
    model, camera = _photo_filters(model, camera)
    if flight is not None and not _PHOTO_ID.fullmatch(flight):
        raise HTTPException(status_code=422, detail="Invalid flight id")
    _no_cache(response)
    try:
        return catalog.list(model=model, camera=camera, flight=flight, limit=limit, offset=offset)
    except (OSError, sqlite3.Error, DjiMediaError) as exc:
        raise HTTPException(status_code=503, detail="Photo catalogue unavailable") from exc


@app.get("/api/v1/photos/map")
def photo_map(request: Request, response: Response,
              model: str | None = Query(default=None, max_length=32),
              camera: str | None = Query(default=None, max_length=32),
              flight: str | None = Query(default=None, max_length=64),
              limit: int = Query(default=10000, ge=1, le=10000),
              authorization: str | None = Header(default=None)) -> dict:
    """Capture positions and flat-terrain footprints derived from EXIF focal length."""
    catalog = _photo_catalog(request, authorization)
    model, camera = _photo_filters(model, camera)
    if flight is not None and not _PHOTO_ID.fullmatch(flight):
        raise HTTPException(status_code=422, detail="Invalid flight id")
    _no_cache(response)
    try:
        return catalog.map_items(model=model, camera=camera, flight=flight, limit=limit)
    except (OSError, sqlite3.Error, DjiMediaError) as exc:
        raise HTTPException(status_code=503, detail="Photo catalogue unavailable") from exc


def _live_streams() -> LiveStreams:
    try:
        return LiveStreams()
    except ValueError as exc:  # misconfigured (non-loopback) MediaMTX URL
        raise HTTPException(status_code=503, detail="Livestream not configured") from exc


def _live_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LiveNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, LiveError):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=503, detail="Livestream-Server (MediaMTX) nicht erreichbar")


def _device_names() -> dict[str, str]:
    runtime = getattr(app.state, "status_runtime", None)
    try:  # resolved names, e.g. the aircraft model detected from its camera payload
        return {v["device_id"]: v["name"] for v in runtime.device_views()} if runtime else {}
    except (AttributeError, KeyError, TypeError):
        return {}


@app.get("/api/v1/live/streams")
async def live_streams(request: Request, response: Response,
                       authorization: str | None = Header(default=None)) -> dict:
    """Active MediaMTX streams (opaque ids, device names; never stream paths)."""
    _require_viewer_access(request, authorization)
    _no_cache(response)
    live = _live_streams()
    try:
        streams = await asyncio.to_thread(live.streams, _device_names())
    except LiveUnavailable:
        return {"available": False, "streams": []}
    return {"available": True, "streams": streams}


@app.post("/api/v1/live/streams/{stream_id}/whep", status_code=201)
async def live_whep_offer(stream_id: str, request: Request,
                          authorization: str | None = Header(default=None),
                          content_type: str | None = Header(default=None)) -> Response:
    """Relay a WebRTC (WHEP) offer; media then flows directly from MediaMTX."""
    _require_viewer_access(request, authorization)
    # application/sdp is not a CORS-safelisted type: cross-site pages cannot post here.
    if (content_type or "").split(";")[0].strip().lower() != "application/sdp":
        raise HTTPException(status_code=415, detail="Content-Type application/sdp required")
    body = await request.body()
    try:
        answer, session = await asyncio.to_thread(_live_streams().offer, stream_id, body)
    except (LiveError, LiveUnavailable) as exc:
        raise _live_http_error(exc) from exc
    return Response(content=answer, status_code=201, media_type="application/sdp",
                    headers={"X-Live-Session": session, "Cache-Control": "no-store"})


@app.delete("/api/v1/live/streams/{stream_id}/whep/{session}", status_code=204)
async def live_whep_close(stream_id: str, session: str, request: Request,
                          authorization: str | None = Header(default=None)) -> Response:
    _require_viewer_access(request, authorization)
    try:
        await asyncio.to_thread(_live_streams().close, stream_id, session)
    except (LiveError, LiveUnavailable) as exc:
        raise _live_http_error(exc) from exc
    return Response(status_code=204)

@app.get("/api/v1/local-cloud/waylines")
async def local_cloud_waylines(request: Request, response: Response,
                               authorization: str | None = Header(default=None)) -> dict:
    """Read-only Pilot 2 Cloud route metadata; no FlightHub dependency.

    The existing session adapter is scoped to local loopback and returns
    only normalized wayline metadata, never access tokens or storage links.
    """
    _require_viewer_access(request, authorization)
    _no_cache(response)
    result = await app.state.local_waylines.read()
    return {
        "state": result["state"],
        "waylines": result.get("waylines", []),
        "reported_total": result.get("reported_total"),
        "pagination_complete": result.get("pagination_complete"),
        "updated_at": result.get("updated_at"),
    }


@app.get("/api/v1/studio/pilot2/action-summary")
async def studio_pilot2_action_summary(request: Request, response: Response,
                                       authorization: str | None = Header(default=None)) -> dict:
    """Authenticated, manually requested, bounded anonymous WPML metadata only."""
    _require_viewer_access(request, authorization)
    _no_cache(response)
    return await app.state.pilot2_action_summary.read()


@app.get("/api/v1/local-cloud/waylines/{wayline_id}/preview")
async def local_cloud_wayline_preview(wayline_id: str, request: Request, response: Response,
                                      authorization: str | None = Header(default=None)) -> dict:
    """Preview an inventoried local cloud KMZ; returns only bounded GeoJSON."""
    _require_viewer_access(request, authorization)
    _no_cache(response)
    try:
        from uuid import UUID
        canonical = str(UUID(wayline_id))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=404, detail="Wayline not found") from None
    inventory = await app.state.local_waylines.read()
    if inventory["state"] != "connected":
        return {"state": inventory["state"], "features": []}
    if not inventory.get("pagination_complete"):
        return {"state": "incomplete_inventory", "features": []}
    available = {route["wayline_id"]: route for route in inventory["waylines"]}
    if canonical not in available:
        raise HTTPException(status_code=404, detail="Wayline not found")
    try:
        credentials = load_credentials(credentials_path())
        if credentials is None or credentials.workspace_id != inventory["workspace_id"]:
            return {"state": "authentication_required", "features": []}
        preview = await asyncio.wait_for(read_preview(credentials, canonical), timeout=22)
    except LocalWaylineError as exc:
        return {"state": str(exc), "features": []}
    except (httpx.HTTPError, OSError, TimeoutError):
        return {"state": "unavailable", "features": []}
    return {"state": "connected", "wayline_id": canonical,
            "name": available[canonical]["name"], **preview}


@app.get("/api/v1/local-cloud/map-elements")
async def local_cloud_map_elements(request: Request, response: Response,
                                   authorization: str | None = Header(default=None)) -> dict:
    """Validated read-only Pilot 2 WGS84 map elements from the local workspace."""
    _require_viewer_access(request, authorization)
    _no_cache(response)
    return await app.state.local_pilot_reader.map_elements()


@app.get("/api/v1/local-cloud/topology")
async def local_cloud_topology(request: Request, response: Response,
                               authorization: str | None = Header(default=None)) -> dict:
    """Read-only RC/aircraft relationships, without upstream personal details."""
    _require_viewer_access(request, authorization)
    _no_cache(response)
    return await app.state.local_pilot_reader.device_topology()


@app.get("/api/v1/local-cloud/diagnostics")
async def local_cloud_diagnostics(request: Request, response: Response,
                                  authorization: str | None = Header(default=None)) -> dict:
    """Safe Pilot 2 GET probe: HTTP and DJI business codes, never body content."""
    _require_viewer_access(request, authorization)
    _no_cache(response)
    return await app.state.local_pilot_reader.diagnostics()


@app.get("/api/v1/flighthub/catalog")
async def flighthub_catalog(request: Request, response: Response,
                            authorization: str | None = Header(default=None)) -> dict:
    """Project library (waylines, models, tasks); local copy only."""
    _no_cache(response)
    _require_viewer_access(request, authorization)
    runtime = app.state.status_runtime
    projects = []
    for (provider, project_id), catalog in runtime.catalog.items():
        project = runtime.inventory._projects.get((provider, project_id))
        projects.append({"provider": provider.value, "project_id": project_id,
                         "name": project.name if project else None, **catalog})
    return {"updated_at": runtime.summary()["flighthub"]["catalog_updated_at"],
            "projects": projects}


TRACK_CACHE_SECONDS = 300
TRACK_CACHE_ENTRIES = 32


@app.get("/api/v1/flighthub/projects/{project_id}/tasks/{task_uuid}/track")
async def flighthub_task_track(project_id: str, task_uuid: str, request: Request,
                               response: Response,
                               authorization: str | None = Header(default=None)):
    """Flown track as GeoJSON. Only tasks listed in the local library are
    fetched, so the endpoint cannot be used to probe arbitrary FlightHub IDs."""
    _no_cache(response)
    _require_viewer_access(request, authorization)
    refresher = app.state.flighthub
    runtime = app.state.status_runtime
    if refresher is None or refresher.settings.config.kind != ProviderKind.PUBLIC_V2:
        raise HTTPException(status_code=404, detail="FlightHub library not enabled")
    catalog = runtime.catalog.get((ProviderKind.PUBLIC_V2, project_id))
    tasks = (catalog or {}).get("tasks") or []
    if not any(task.get("uuid") == task_uuid for task in tasks):
        raise HTTPException(status_code=404, detail="Unknown flight task")
    key = (project_id, task_uuid)
    cache = app.state.track_cache
    cached = cache.get(key)
    if cached is None or time.monotonic() - cached[0] > TRACK_CACHE_SECONDS:
        try:
            feature = await read_task_track(refresher.settings.config, project_id, task_uuid)
        except (ValueError, RuntimeError):
            # Provider error text is not forwarded.
            raise HTTPException(status_code=502, detail="Track not available from FlightHub")
        if len(cache) >= TRACK_CACHE_ENTRIES:
            cache.pop(min(cache, key=lambda k: cache[k][0]))
        cache[key] = cached = (time.monotonic(), feature)
    return JSONResponse(cached[1], media_type="application/geo+json",
                        headers=dict(response.headers))


@app.get("/api/v1/flighthub/projects/{project_id}/tasks/{task_uuid}/media")
async def flighthub_task_media(project_id: str, task_uuid: str, request: Request,
                              response: Response,
                              authorization: str | None = Header(default=None)) -> dict:
    """DJI task media metadata only. Never expose expiring storage URLs.

    FlightHub's GET /flight-task/{uuid}/media may include signed preview and
    original download URLs; these are discarded in flighthub_catalog.
    Both project and task must already exist in the local read-only cache.
    """
    _no_cache(response)
    _require_viewer_access(request, authorization)
    refresher = app.state.flighthub
    runtime = app.state.status_runtime
    if refresher is None or refresher.settings.config.kind != ProviderKind.PUBLIC_V2:
        raise HTTPException(status_code=404, detail="FlightHub library not enabled")
    catalog = runtime.catalog.get((ProviderKind.PUBLIC_V2, project_id))
    tasks = (catalog or {}).get("tasks") or []
    if not any(task.get("uuid") == task_uuid for task in tasks):
        raise HTTPException(status_code=404, detail="Unknown flight task")
    key = (project_id, task_uuid)
    cache = app.state.task_media_cache
    cached = cache.get(key)
    if cached is None or time.monotonic() - cached[0] > TRACK_CACHE_SECONDS:
        try:
            media = await read_task_media(refresher.settings.config, project_id, task_uuid)
        except (ValueError, RuntimeError):
            raise HTTPException(status_code=502, detail="Task media not available from FlightHub")
        if len(cache) >= TRACK_CACHE_ENTRIES:
            cache.pop(min(cache, key=lambda k: cache[k][0]))
        cache[key] = cached = (time.monotonic(), list(media))
    return {"task_uuid": task_uuid, "project_id": project_id,
            "total": len(cached[1]), "media": cached[1]}


@app.get("/status", response_class=HTMLResponse)
async def status_page(request: Request, response: Response) -> str:
    """Token-free LAN shell; static content never contains live DJI secrets."""
    if lan_mode_enabled():
        require_lan(request)
    _no_cache(response)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; script-src 'unsafe-inline'; "
        "style-src 'unsafe-inline'; connect-src 'self'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
    )
    return render_page(app.state.status_runtime.settings.refresh_every_seconds)



# Local design workspace: these endpoints write ONLY to the Pi user's private
# disk, never to DJI. All data endpoints require the separate dashboard token.
def _studio_workspace(request: Request, authorization: str | None) -> Workspace:
    _require_viewer_access(request, authorization)
    try:
        return Workspace()
    except (OSError, WorkspaceError) as exc:
        raise HTTPException(status_code=503, detail="Private workspace unavailable") from exc


def _studio_error(exc: WorkspaceError) -> HTTPException:
    return HTTPException(status_code=404 if "not found" in str(exc).lower() else 400,
                         detail=str(exc))


@app.get("/operations", response_class=HTMLResponse, include_in_schema=False)
def operations_page(request: Request, response: Response) -> str:
    """Local FlightHub-inspired read-only project and cockpit overview."""
    if lan_mode_enabled():
        require_lan(request)
    _no_cache(response)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: blob: https://cdn.jsdelivr.net https://tile.openstreetmap.org "
        "https://server.arcgisonline.com; "
        "connect-src 'self' https://tile.openstreetmap.org https://server.arcgisonline.com; "
        "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    )
    return render_operations()


@app.get("/media", response_class=HTMLResponse, include_in_schema=False)
def dji_media_page(request: Request, response: Response) -> str:
    """Static read-only DJI MinIO index browser; never contains credentials."""
    if lan_mode_enabled():
        require_lan(request)
    _no_cache(response)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; script-src 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' blob: data: https://cdn.jsdelivr.net https://tile.openstreetmap.org https://server.arcgisonline.com; "
        "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
    )
    return render_dji_media_page()


@app.get("/api/v1/cloudapi2/devices")
async def cloud_api2_devices(request: Request, response: Response,
                             authorization: str | None = Header(default=None)) -> dict:
    """Optional read-only DJI Cloud API 2 BFF source (server-to-server only).

    Browser never receives backend credentials. Only the exact SDK skeleton
    device-list GET is permitted; aircraft only, no dock or flight commands.
    """
    _no_cache(response)
    _require_viewer_access(request, authorization)
    bridge = app.state.cloud_api2_bridge
    if bridge is None:
        return {"source": "dji-cloud-api-2", "state": "disabled",
                "devices": [], "total": 0}
    return await bridge.read()


def _studio_socket_origin() -> str:
    """WSS origin for the optional studio events socket, from configuration."""
    host = lan_host()
    port = os.environ.get("AERONEXUS_PORT", "8000").strip()
    if host is None or not port.isdigit() or not 1 <= int(port) <= 65535:
        return ""
    return f"wss://{host}:{int(port)} "


@app.get("/studio", response_class=HTMLResponse, include_in_schema=False)
def studio_page(request: Request, response: Response) -> str:
    """Static studio shell without tokens or embedded private data."""
    if lan_mode_enabled():
        require_lan(request)
    _no_cache(response)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' blob: data: https://cdn.jsdelivr.net https://tile.openstreetmap.org "
        "https://server.arcgisonline.com; "
        f"connect-src 'self' {_studio_socket_origin()}https://tile.openstreetmap.org https://server.arcgisonline.com; "
        "media-src 'self' blob:; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'none'"
    )
    return render_studio()


@app.get("/api/v1/studio/missions")
def studio_missions(request: Request, response: Response,
                    authorization: str | None = Header(default=None)) -> dict:
    _no_cache(response)
    return {"missions": _studio_workspace(request, authorization).list_missions()}


@app.post("/api/v1/studio/missions", status_code=201)
def studio_create_mission(mission: WaypointMission, request: Request,
                          response: Response,
                          authorization: str | None = Header(default=None)) -> dict:
    _no_cache(response)
    try:
        return _studio_workspace(request, authorization).save_mission(mission)
    except WorkspaceError as exc:
        raise _studio_error(exc) from exc


@app.get("/api/v1/studio/missions/reconciliation")
async def studio_mission_reconciliation(request: Request, response: Response,
                                  authorization: str | None = Header(default=None)) -> dict:
    _no_cache(response)
    workspace = _studio_workspace(request, authorization)
    runtime = app.state.status_runtime
    local = await app.state.local_waylines.read()
    return compare_missions(workspace.list_missions(), runtime.catalog,
                            runtime.summary()["flighthub"]["catalog_updated_at"], local)


@app.options("/api/v1/local-cloud/session", include_in_schema=False)
def local_cloud_session_preflight(request: Request) -> Response:
    origin = handoff_origin(request)
    if (request.headers.get("access-control-request-method") != "POST"
            or request.headers.get("access-control-request-headers", "").lower() != "content-type"):
        raise HTTPException(403, "Unsupported session handoff request")
    return Response(status_code=204, headers={
        "Access-Control-Allow-Origin": origin, "Vary": "Origin", "Cache-Control": "no-store",
        "Access-Control-Allow-Methods": "POST", "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Max-Age": "600"})


@app.post("/api/v1/local-cloud/session", include_in_schema=False)
async def local_cloud_session_handoff(request: Request) -> Response:
    origin = handoff_origin(request)
    headers = {"Access-Control-Allow-Origin": origin, "Vary": "Origin", "Cache-Control": "no-store"}
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        return JSONResponse({"state": "invalid_session"}, status_code=415, headers=headers)
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > 16384:
            return JSONResponse({"state": "invalid_session"}, status_code=413, headers=headers)
        content.extend(chunk)
    try:
        import json
        credentials = Credentials.parse(json.loads(content))
        await app.state.local_session_handoff.accept(credentials)
    except LocalWaylineError as exc:
        return JSONResponse({"state": str(exc)}, status_code=409 if str(exc) == "workspace_conflict" else 403, headers=headers)
    except (ValueError, UnicodeError, RecursionError):
        return JSONResponse({"state": "invalid_session"}, status_code=400, headers=headers)
    except (OSError, TimeoutError):
        return JSONResponse({"state": "session_unavailable"}, status_code=503, headers=headers)
    return Response(status_code=204, headers=headers)


@app.post("/api/v1/studio/missions/preview.csv")
async def studio_preview_csv(request: Request, response: Response,
                             delimiter: str = "semicolon", decimal: str = "dot",
                             close_route: bool = False,
                             authorization: str | None = Header(default=None)) -> dict:
    """Authenticated, non-persistent CSV preview; existing mission save remains explicit."""
    _require_viewer_access(request, authorization)
    _no_cache(response)
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > MAX_CSV_BYTES:
            raise HTTPException(status_code=413, detail="CSV darf maximal 512 KiB groß sein.")
        content.extend(chunk)
    try:
        return preview_csv(bytes(content), delimiter=delimiter, decimal=decimal,
                           close_route=close_route)
    except MissionCsvError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/studio/missions/import.kmz", status_code=201)
async def studio_import_mission(request: Request, response: Response,
                                authorization: str | None = Header(default=None)) -> dict:
    """Only re-import AeroNexus-generated waypoint KMZ into local drafts."""
    store = _studio_workspace(request, authorization)
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > 2 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="KMZ import maximum 2 MiB")
    try:
        mission = import_kmz(bytes(content))
        result = store.save_mission(mission)
    except WorkspaceError as exc:
        raise _studio_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Unsupported or invalid AeroNexus waypoint KMZ") from exc
    _no_cache(response)
    return result


@app.get("/api/v1/studio/missions/{mission_id}")
def studio_get_mission(mission_id: str, request: Request, response: Response,
                       authorization: str | None = Header(default=None)) -> dict:
    _no_cache(response)
    try:
        return _studio_workspace(request, authorization).get_mission(mission_id)
    except WorkspaceError as exc:
        raise _studio_error(exc) from exc


@app.put("/api/v1/studio/missions/{mission_id}")
def studio_update_mission(mission_id: str, mission: WaypointMission,
                          request: Request, response: Response,
                          authorization: str | None = Header(default=None)) -> dict:
    _no_cache(response)
    try:
        return _studio_workspace(request, authorization).save_mission(mission, mission_id)
    except WorkspaceError as exc:
        raise _studio_error(exc) from exc


@app.delete("/api/v1/studio/missions/{mission_id}", status_code=204)
def studio_delete_mission(mission_id: str, request: Request, response: Response,
                          authorization: str | None = Header(default=None)) -> None:
    _no_cache(response)
    try:
        _studio_workspace(request, authorization).delete_mission(mission_id)
    except WorkspaceError as exc:
        raise _studio_error(exc) from exc


@app.get("/api/v1/studio/missions/{mission_id}/export.kmz")
def studio_export_mission(mission_id: str, request: Request,
                          authorization: str | None = Header(default=None)):
    store = _studio_workspace(request, authorization)
    try:
        mission = WaypointMission.model_validate(store.get_mission(mission_id)["mission"])
        result = export_kmz(mission, timestamp_ms=int(time.time() * 1000))
    except WorkspaceError as exc:
        raise _studio_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return StreamingResponse(
        BytesIO(result), media_type="application/vnd.google-earth.kmz",
        headers={"Content-Disposition": f'attachment; filename="aeronexus-{mission_id}.kmz"',
                 "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@app.get("/api/v1/studio/media")
def studio_media_list(request: Request, response: Response,
                      authorization: str | None = Header(default=None)) -> dict:
    _no_cache(response)
    return {"media": _studio_workspace(request, authorization).list_media()}


# The DJI MinIO catalogue is separate from the editable local media library.
# The re-indexing operation runs explicitly on the Pi; HTTP is read-only.
@app.get("/api/v1/studio/dji-media")
def studio_dji_media_list(request: Request, response: Response,
                          q: str = Query(default="", max_length=120),
                          limit: int = Query(default=100, ge=1, le=200),
                          offset: int = Query(default=0, ge=0, le=1_000_000),
                          authorization: str | None = Header(default=None)) -> dict:
    workspace = _studio_workspace(request, authorization)
    _no_cache(response)
    try:
        return DjiMediaIndex(workspace.root).list(query=q, limit=limit, offset=offset)
    except (OSError, sqlite3.Error, DjiMediaError) as exc:
        raise HTTPException(status_code=503, detail="DJI media index unavailable") from exc


@app.get("/api/v1/studio/dji-media/{media_id}/file")
def studio_dji_media_file(media_id: str, request: Request,
                          authorization: str | None = Header(default=None),
                          download: bool = Query(default=False)):
    """Read MinIO by indexed opaque id only, never by caller-supplied key.

    Only explicit file requests contact MinIO. Unknown/raw media can be
    downloaded, but only small browser-safe images can be previewed inline.
    """
    workspace = _studio_workspace(request, authorization)
    try:
        record = DjiMediaIndex(workspace.root).get(media_id)
    except (OSError, sqlite3.Error, DjiMediaError) as exc:
        raise HTTPException(status_code=503, detail="DJI media index unavailable") from exc
    if record is None:
        raise HTTPException(status_code=404, detail="DJI media not indexed")
    if (not download and (record["mime"] not in BROWSER_PREVIEW_MIMES
                          or record["size_bytes"] > MAX_BROWSER_PREVIEW_BYTES)):
        raise HTTPException(status_code=415, detail="Preview unavailable; use download")
    try:
        settings = MinioMediaSettings.from_env()
        if settings.bucket != record["bucket"]:
            raise HTTPException(status_code=503, detail="DJI media bucket changed")
        client = minio_client(settings)
        head = client.stat_object(record["bucket"], record["object_key"])
        if head.size != record["size_bytes"] or head.etag != record["etag"]:
            raise HTTPException(status_code=409, detail="DJI media changed; reindex required")
        stream = client.get_object(record["bucket"], record["object_key"])
    except HTTPException:
        raise
    except (DjiMediaError, OSError) as exc:
        raise HTTPException(status_code=503, detail="MinIO media reader unavailable") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="MinIO object unavailable") from exc

    def chunks():
        try:
            yield from stream.stream(64 * 1024)
        finally:
            stream.close()
            stream.release_conn()

    # No object keys, S3 URLs, credentials or DJI identifiers in headers.
    disposition = "attachment" if download else "inline"
    return StreamingResponse(chunks(), media_type=record["mime"],
                             headers={
                                 "Cache-Control": "no-store",
                                 "X-Content-Type-Options": "nosniff",
                                 "Referrer-Policy": "no-referrer",
                                 "Content-Length": str(record["size_bytes"]),
                                 "Content-Disposition": disposition,
                             })


@app.post("/api/v1/studio/media", status_code=201)
async def studio_media_upload(request: Request, response: Response,
                              authorization: str | None = Header(default=None),
                              x_filename: str | None = Header(default=None)) -> dict:
    """Raw binary upload: no multipart parser, 25 MiB hard streamed cap."""
    store = _studio_workspace(request, authorization)
    mime = (request.headers.get("content-type") or "").split(";", 1)[0].lower()
    if mime not in MEDIA_TYPES or not x_filename or len(x_filename) > 400:
        raise HTTPException(status_code=415, detail="Supported: JPEG, PNG, WebP, MP4")
    length = request.headers.get("content-length")
    if length is not None:
        try:
            if int(length) > MAX_MEDIA_BYTES:
                raise HTTPException(status_code=413, detail="Maximum media size is 25 MiB")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid Content-Length") from exc
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > MAX_MEDIA_BYTES:
            raise HTTPException(status_code=413, detail="Maximum media size is 25 MiB")
    try:
        result = store.save_media(filename=unquote(x_filename), mime=mime,
                                  content=bytes(content))
    except WorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _no_cache(response)
    return result


@app.get("/api/v1/studio/media/{media_id}/file")
def studio_media_download(media_id: str, request: Request,
                          authorization: str | None = Header(default=None)):
    try:
        meta, path = _studio_workspace(request, authorization).get_media(media_id)
    except WorkspaceError as exc:
        raise _studio_error(exc) from exc
    return FileResponse(
        path, media_type=meta["mime"],
        filename=path.name, content_disposition_type="attachment",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@app.delete("/api/v1/studio/media/{media_id}", status_code=204)
def studio_media_delete(media_id: str, request: Request, response: Response,
                        authorization: str | None = Header(default=None)) -> None:
    _no_cache(response)
    try:
        _studio_workspace(request, authorization).delete_media(media_id)
    except WorkspaceError as exc:
        raise _studio_error(exc) from exc





class GeoPhotoPatch(BaseModel):
    """Manually assigned WGS84 photo metadata; never infer unsupported EXIF."""
    model_config=ConfigDict(extra="forbid")
    latitude: float | None = Field(default=None,ge=-90,le=90,allow_inf_nan=False)
    longitude: float | None = Field(default=None,ge=-180,le=180,allow_inf_nan=False)
    altitude_m: float | None = Field(default=None,ge=-500,le=12000,allow_inf_nan=False)
    heading_deg: float | None = Field(default=None,ge=0,lt=360,allow_inf_nan=False)
    pitch_deg: float | None = Field(default=None,ge=-90,le=90,allow_inf_nan=False)
    roll_deg: float | None = Field(default=None,ge=-180,le=180,allow_inf_nan=False)
    captured_at: datetime | None = None
    notes: str = Field(default="",max_length=512)

    @model_validator(mode="after")
    def geo_pair(self):
        if (self.latitude is None)!=(self.longitude is None):
            raise ValueError("Latitude and longitude must be supplied together")
        if self.captured_at is not None and self.captured_at.utcoffset() is None:
            raise ValueError("Capture timestamp must include timezone")
        return self


@app.websocket("/api/v1/studio/events")
async def studio_events(socket: WebSocket) -> None:
    """Opt-in LAN-only cached-status invalidations; read-only by design."""
    await serve_studio_events(socket, app.state.status_runtime, app.state)


@app.get("/api/v1/studio/geo-objects")
def studio_geo_objects(request: Request,response: Response,
                       authorization: str | None=Header(default=None)) -> dict:
    _no_cache(response)
    return {"objects":_studio_workspace(request,authorization).list_geo_objects()}


@app.post("/api/v1/studio/geo-objects",status_code=201)
def studio_geo_add(obj: GeoObject,request: Request,response: Response,
                   authorization: str | None=Header(default=None)) -> dict:
    _no_cache(response)
    try:
        return _studio_workspace(request,authorization).save_geo_object(obj)
    except WorkspaceError as exc:
        raise _studio_error(exc) from exc


@app.put("/api/v1/studio/geo-objects/{geo_id}")
def studio_geo_update(geo_id:str,obj:GeoObject,request:Request,response:Response,
                      authorization:str|None=Header(default=None))->dict:
    _no_cache(response)
    try:
        return _studio_workspace(request,authorization).save_geo_object(obj,geo_id)
    except WorkspaceError as exc:
        raise _studio_error(exc) from exc


@app.delete("/api/v1/studio/geo-objects/{geo_id}",status_code=204)
def studio_geo_delete(geo_id:str,request:Request,response:Response,
                      authorization:str|None=Header(default=None))->None:
    _no_cache(response)
    try:
        _studio_workspace(request,authorization).delete_geo_object(geo_id)
    except WorkspaceError as exc:
        raise _studio_error(exc) from exc


@app.post("/api/v1/studio/survey/preview")
def studio_survey_preview(plan:SurveyPlanRequest,request:Request,response:Response,
                          authorization:str|None=Header(default=None))->dict:
    _require_viewer_access(request,authorization)
    _no_cache(response)
    try:
        return generate_survey_preview(plan)
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc


@app.patch("/api/v1/studio/media/{media_id}/geo")
def studio_media_geo_update(media_id:str,geo:GeoPhotoPatch,request:Request,
                            response:Response,
                            authorization:str|None=Header(default=None))->dict:
    _no_cache(response)
    try:
        store=_studio_workspace(request,authorization)
        meta,_=store.get_media(media_id)
        if not meta["mime"].startswith("image/"):
            raise HTTPException(status_code=422,detail="GeoPhoto requires an image")
        return store.update_media_georef(
            media_id,latitude=geo.latitude,longitude=geo.longitude,
            heading_deg=geo.heading_deg,pitch_deg=geo.pitch_deg,
            roll_deg=geo.roll_deg,altitude_m=geo.altitude_m,
            captured_at=geo.captured_at.isoformat() if geo.captured_at else None,
            notes=geo.notes)
    except WorkspaceError as exc:
        raise _studio_error(exc) from exc


@app.post("/api/v1/studio/terrain/geotiff")
async def studio_terrain_geotiff(request:Request,response:Response,
                               authorization:str|None=Header(default=None))->dict:
    """Bounded transient GeoTIFF sampler; optional GDAL, no persisted upload."""
    _require_viewer_access(request,authorization)
    content=bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content)>8*1024*1024:
            raise HTTPException(status_code=413,detail="Maximum GeoTIFF upload 8 MiB")
    geo_info={}
    try:
        grid=geotiff_preview(bytes(content),geo_info=geo_info)
    except TerrainUnavailable as exc:
        raise HTTPException(status_code=503,detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
    _no_cache(response)
    return {"grid":grid.model_dump(),"overview":terrain_overview(grid),
            "geo":geo_info or None}


@app.post("/api/v1/studio/terrain/export.stl")
def studio_terrain_stl(grid:TerrainGrid,request:Request,
                       authorization:str|None=Header(default=None)):
    _require_viewer_access(request,authorization)
    return Response(content=terrain_stl(grid),media_type="model/stl",
                    headers={"Content-Disposition":'attachment; filename="aeronexus-terrain.stl"',
                             "Cache-Control":"no-store","X-Content-Type-Options":"nosniff"})


# Thermal: DJI R-JPEGs from the read-only MinIO index, temperatures only
# from the DJI Thermal SDK (separate process). Originals are never modified.
def _thermal_service(request: Request, authorization: str | None) -> ThermalService:
    workspace = _studio_workspace(request, authorization)
    service = getattr(app.state, "thermal_service", None)
    if service is None or service.index.root != workspace.root:
        service = app.state.thermal_service = ThermalService(DjiMediaIndex(workspace.root))
    return service


def _thermal_params(distance, humidity, emissivity, reflection, ambient) -> MeasureParams:
    try:
        return MeasureParams(distance=distance, humidity=humidity, emissivity=emissivity,
                             reflection=reflection, ambient=ambient)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _thermal_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ThermalNotFound):
        return HTTPException(status_code=404, detail="Thermal image not indexed")
    if isinstance(exc, ThermalChanged):
        return HTTPException(status_code=409, detail="DJI media changed; reindex required")
    if isinstance(exc, ThermalSdkBusy):
        return HTTPException(status_code=503, detail="DJI Thermal SDK is busy",
                             headers={"Retry-After": "5"})
    if isinstance(exc, ThermalSdkUnavailable):
        return HTTPException(status_code=503, detail="DJI Thermal SDK not available")
    if isinstance(exc, (ThermalError, ThermalSdkError)):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=503, detail="DJI media unavailable")


_THERMAL_ERRORS = (ThermalError, ThermalSdkError, DjiMediaError, OSError, sqlite3.Error)
_Param = lambda: Query(default=None)  # noqa: E731


@app.get("/thermal", response_class=HTMLResponse, include_in_schema=False)
def thermal_page(request: Request, response: Response) -> str:
    if lan_mode_enabled():
        require_lan(request)
    _no_cache(response)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; script-src 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' blob: data: https://cdn.jsdelivr.net https://tile.openstreetmap.org https://server.arcgisonline.com; "
        "connect-src 'self'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
    )
    return render_thermal_page()


@app.get("/api/v1/thermal/status")
def thermal_status(request: Request, response: Response,
                   authorization: str | None = Header(default=None)) -> dict:
    service = _thermal_service(request, authorization)
    _no_cache(response)
    try:
        listing = service.index.list_thermal(limit=1, extra_ids=service.extra_thermal_ids())
    except (DjiMediaError, OSError, sqlite3.Error):
        listing = {"total": None, "last_scanned_at": None}
    return {"sdk": service.sdk_status(), "thermal_images": listing["total"],
            "last_scanned_at": listing["last_scanned_at"]}


@app.get("/api/v1/thermal/images")
def thermal_images(request: Request, response: Response,
                   q: str = Query(default="", max_length=120),
                   limit: int = Query(default=50, ge=1, le=100),
                   offset: int = Query(default=0, ge=0, le=1_000_000),
                   authorization: str | None = Header(default=None)) -> dict:
    service = _thermal_service(request, authorization)
    _no_cache(response)
    try:
        return service.list(query=q, limit=limit, offset=offset)
    except _THERMAL_ERRORS as exc:
        raise _thermal_http_error(exc) from exc


def _thermal_flights(request: Request, authorization: str | None) -> ThermalFlights:
    service = _thermal_service(request, authorization)
    flights = getattr(service, "flights", None)
    if flights is None:
        flights = service.flights = ThermalFlights(service)
    return flights


_GEO_ERRORS = (DjiMediaError, OSError, sqlite3.Error, ValueError)


@app.get("/api/v1/thermal/map")
def thermal_map(request: Request, response: Response,
                authorization: str | None = Header(default=None)) -> dict:
    """Positions, near-nadir footprints, flight ids and cached per-image stats."""
    flights = _thermal_flights(request, authorization)
    _no_cache(response)
    try:
        return flights.map_items()
    except _GEO_ERRORS as exc:
        raise HTTPException(status_code=503, detail="Thermal geo index unavailable") from exc


@app.get("/api/v1/thermal/flights")
def thermal_flights(request: Request, response: Response,
                    authorization: str | None = Header(default=None)) -> dict:
    flights = _thermal_flights(request, authorization)
    _no_cache(response)
    try:
        return flights.flights()
    except _GEO_ERRORS as exc:
        raise HTTPException(status_code=503, detail="Thermal geo index unavailable") from exc


@app.get("/api/v1/thermal/flights/{flight_id}")
def thermal_flight(flight_id: str, request: Request, response: Response,
                   limit: int = Query(default=200, ge=1, le=1000),
                   authorization: str | None = Header(default=None)) -> dict:
    """Hotspot ranking of one flight (images sorted by maximum temperature)."""
    flights = _thermal_flights(request, authorization)
    _no_cache(response)
    try:
        return flights.flight_detail(flight_id, limit=limit)
    except ThermalNotFound as exc:
        raise HTTPException(status_code=404, detail="Unknown flight") from exc
    except _GEO_ERRORS as exc:
        raise HTTPException(status_code=503, detail="Thermal geo index unavailable") from exc


@app.post("/api/v1/thermal/flights/{flight_id}/analyze", status_code=202)
def thermal_flight_analyze(flight_id: str, request: Request, response: Response,
                           authorization: str | None = Header(default=None)) -> dict:
    """Start the background SDK measurement of all not yet measured images.

    Writes only the private local summary cache; nothing is written to MinIO/DJI."""
    flights = _thermal_flights(request, authorization)
    _no_cache(response)
    try:
        return flights.start(flight_id)
    except ThermalNotFound as exc:
        raise HTTPException(status_code=404, detail="Unknown flight") from exc
    except ThermalJobRunning as exc:
        raise HTTPException(status_code=409, detail="A flight analysis is already running") from exc
    except _GEO_ERRORS as exc:
        raise HTTPException(status_code=503, detail="Thermal geo index unavailable") from exc


@app.get("/api/v1/thermal/jobs/current")
def thermal_job(request: Request, response: Response,
                authorization: str | None = Header(default=None)) -> dict:
    flights = _thermal_flights(request, authorization)
    _no_cache(response)
    return flights.job()


@app.post("/api/v1/thermal/jobs/current/cancel")
def thermal_job_cancel(request: Request, response: Response,
                       authorization: str | None = Header(default=None)) -> dict:
    flights = _thermal_flights(request, authorization)
    _no_cache(response)
    return flights.cancel()


@app.get("/api/v1/thermal/images/{media_id}/analysis")
def thermal_analysis(media_id: str, request: Request, response: Response,
                     distance: float | None = _Param(), humidity: float | None = _Param(),
                     emissivity: float | None = _Param(), reflection: float | None = _Param(),
                     ambient: float | None = _Param(),
                     authorization: str | None = Header(default=None)) -> dict:
    service = _thermal_service(request, authorization)
    params = _thermal_params(distance, humidity, emissivity, reflection, ambient)
    _no_cache(response)
    try:
        return service.analysis(media_id, params)
    except _THERMAL_ERRORS as exc:
        raise _thermal_http_error(exc) from exc


@app.get("/api/v1/thermal/images/{media_id}/pv")
def thermal_pv_inspection(
        media_id: str, request: Request, response: Response,
        distance: float | None = _Param(), humidity: float | None = _Param(),
        emissivity: float | None = _Param(), reflection: float | None = _Param(),
        ambient: float | None = _Param(),
        x: int | None = Query(default=None, ge=0, le=8192), y: int | None = Query(default=None, ge=0, le=8192),
        w: int | None = Query(default=None, ge=2, le=8192), h: int | None = Query(default=None, ge=2, le=8192),
        detect_k: float = Query(default=3.0), class2_k: float = Query(default=10.0),
        class3_k: float = Query(default=20.0), min_pixels: int = Query(default=4),
        cell_size_m: float = Query(default=0.166),
        irradiance: float | None = _Param(), wind: float | None = _Param(),
        cloud: float | None = _Param(), tilt: float | None = _Param(),
        azimuth: float | None = _Param(),
        authorization: str | None = Header(default=None)) -> dict:
    """PV abnormalities (ΔT vs. median of the PV area) and condition checklist."""
    service = _thermal_service(request, authorization)
    params = _thermal_params(distance, humidity, emissivity, reflection, ambient)
    _no_cache(response)
    try:
        region = Region(x, y, w, h) if None not in (x, y, w, h) else None
        thresholds = PvThresholds(detect_k, class2_k, class3_k, min_pixels, cell_size_m)
        conditions = PvConditions(irradiance, wind, cloud, tilt, azimuth)
    except PvInspectionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        return service.pv_inspection(media_id, params, region, thresholds, conditions)
    except PvInspectionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except _THERMAL_ERRORS as exc:
        raise _thermal_http_error(exc) from exc


@app.get("/api/v1/thermal/images/{media_id}/temperatures")
def thermal_temperatures(media_id: str, request: Request,
                         distance: float | None = _Param(), humidity: float | None = _Param(),
                         emissivity: float | None = _Param(), reflection: float | None = _Param(),
                         ambient: float | None = _Param(),
                         authorization: str | None = Header(default=None)) -> Response:
    """Row-major float32 little-endian deg C grid (X-Thermal-Width x X-Thermal-Height)."""
    service = _thermal_service(request, authorization)
    params = _thermal_params(distance, humidity, emissivity, reflection, ambient)
    try:
        measurement = service.measure(media_id, params)
    except _THERMAL_ERRORS as exc:
        raise _thermal_http_error(exc) from exc
    grid = measurement.grid
    if sys.byteorder != "little":
        grid = type(grid)(grid)
        grid.byteswap()
    return Response(content=grid.tobytes(), media_type="application/octet-stream", headers={
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "X-Thermal-Width": str(measurement.width), "X-Thermal-Height": str(measurement.height),
    })


# Multispectral (DJI Mavic 3M): bands from the read-only MinIO index, processed
# per DJI's M3M Image Processing Guide. Catalogue scans run explicitly on the Pi.
def _ms_service(request: Request, authorization: str | None) -> MultispectralService:
    workspace = _studio_workspace(request, authorization)
    service = getattr(app.state, "ms_service", None)
    if service is None or service.media.root != workspace.root:
        service = app.state.ms_service = MultispectralService(DjiMediaIndex(workspace.root))
    return service


def _ms_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, MultispectralNotFound):
        return HTTPException(status_code=404, detail="Multispectral capture or band not indexed")
    if isinstance(exc, DjiMediaChanged):
        return HTTPException(status_code=409, detail="DJI media changed; reindex required")
    if isinstance(exc, MultispectralBusy):
        return HTTPException(status_code=503, detail="Multispectral processing busy",
                             headers={"Retry-After": "10"})
    if isinstance(exc, MultispectralError):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=503, detail="DJI media unavailable")


_MS_ERRORS = (MultispectralError, DjiMediaError, OSError, sqlite3.Error)
_MS_REPORT_SLOT = threading.BoundedSemaphore(1)


class MultispectralReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capture_uuids: list[Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]] = Field(min_length=1, max_length=20)
    layers: list[Literal["ndvi", "ndre", "gndvi", "lci"]] = Field(
        default_factory=lambda: ["ndvi", "ndre", "gndvi", "lci"], min_length=1, max_length=4)
    scale: Literal[1, 2, 4] = 4
    ndvi_threshold: float | None = Field(default=None, ge=-1, le=1, allow_inf_nan=False)


@app.post("/api/v1/multispectral/reports")
def multispectral_report(body: MultispectralReportRequest, request: Request, response: Response,
                         format: Literal["json", "csv"] = "json",
                         authorization: str | None = Header(default=None)):
    service = _ms_service(request, authorization)
    _no_cache(response)
    if not _MS_REPORT_SLOT.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="Ein Serienbericht wird bereits berechnet. Erneut versuchen.",
                            headers={"Retry-After": "5"})
    try:
        report = build_report(service, body.capture_uuids, body.layers, scale=body.scale,
                              threshold=body.ndvi_threshold)
        if format == "csv":
            result = Response(report_csv(report), media_type="text/csv; charset=utf-8",
                              headers={"Content-Disposition": 'attachment; filename="m3m_serienbericht.csv"'})
            _no_cache(result)
            return result
        return report
    except _MS_ERRORS as exc:
        raise _ms_http_error(exc) from exc
    finally:
        _MS_REPORT_SLOT.release()


def _raster_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, RasterNotFound):
        return HTTPException(404, str(exc))
    if isinstance(exc, RasterChanged):
        return HTTPException(409, str(exc))
    if isinstance(exc, (RasterBusy, RasterUnavailable)):
        return HTTPException(503, str(exc))
    if isinstance(exc, RasterError):
        return HTTPException(422, str(exc))
    return HTTPException(503, "Ergebnisraster nicht verfügbar; Datei und Katalog prüfen.")


@app.get("/results", response_class=HTMLResponse, include_in_schema=False)
def results_page(request: Request, response: Response) -> str:
    if lan_mode_enabled():
        require_lan(request)
    _no_cache(response)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; script-src 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
        "frame-ancestors 'none'; form-action 'none'"
    )
    return render_results_page()


@app.get("/api/v1/results")
def raster_results_list(request: Request, response: Response,
                        q: str = Query(default="", max_length=120),
                        limit: int = Query(default=50, ge=1, le=100),
                        offset: int = Query(default=0, ge=0),
                        authorization: str | None = Header(default=None)) -> dict:
    _require_viewer_access(request, authorization)
    _no_cache(response)
    try:
        service = RasterResults()
        result = service.list(query=q, limit=limit, offset=offset)
        try:
            _libraries()
            result["raster_available"] = True
        except RasterUnavailable:
            result["raster_available"] = False
        return result
    except Exception as exc:
        raise _raster_http_error(exc) from exc


@app.post("/api/v1/results/scan")
def raster_results_scan(request: Request, response: Response,
                        authorization: str | None = Header(default=None)) -> dict:
    _require_viewer_access(request, authorization)
    _no_cache(response)
    try:
        return RasterResults().scan()
    except Exception as exc:
        raise _raster_http_error(exc) from exc


@app.get("/api/v1/results/{result_id}")
def raster_result(result_id: str, request: Request, response: Response,
                  authorization: str | None = Header(default=None)) -> dict:
    _require_viewer_access(request, authorization)
    _no_cache(response)
    try:
        return RasterResults().get(result_id)[0]
    except Exception as exc:
        raise _raster_http_error(exc) from exc


@app.get("/api/v1/results/{result_id}/statistics")
def raster_statistics(result_id: str, request: Request, response: Response,
                      band: int = Query(default=1, ge=1, le=16), v: str | None = None,
                      authorization: str | None = Header(default=None)) -> dict:
    _require_viewer_access(request, authorization)
    _no_cache(response)
    try:
        return RasterResults().statistics(result_id, band, v)
    except Exception as exc:
        raise _raster_http_error(exc) from exc


@app.get("/api/v1/results/{result_id}/tiles/{z}/{x}/{y}.png")
def raster_tile(result_id: str, z: int, x: int, y: int, request: Request,
                band: int = Query(default=1, ge=1, le=16), mode: str = "scalar",
                palette: str = "viridis", low: float = 0., high: float = 1.,
                v: str | None = None,
                authorization: str | None = Header(default=None)) -> Response:
    _require_viewer_access(request, authorization)
    try:
        png = RasterResults().tile(result_id, z, x, y, band=band, mode=mode,
                                   palette=palette, low=low, high=high, version=v)
        return Response(content=png, media_type="image/png", headers={"Cache-Control": "no-store",
                        "X-Content-Type-Options": "nosniff"})
    except Exception as exc:
        raise _raster_http_error(exc) from exc


@app.get("/multispectral", response_class=HTMLResponse, include_in_schema=False)
def multispectral_page(request: Request, response: Response) -> str:
    if lan_mode_enabled():
        require_lan(request)
    _no_cache(response)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; script-src 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' blob: data: https://cdn.jsdelivr.net https://tile.openstreetmap.org https://server.arcgisonline.com; "
        "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
    )
    return render_multispectral_page()


@app.get("/api/v1/multispectral/captures")
def multispectral_captures(request: Request, response: Response,
                           authorization: str | None = Header(default=None)) -> dict:
    service = _ms_service(request, authorization)
    _no_cache(response)
    try:
        captures = service.catalog.captures()
        return {"captures": captures, "total": len(captures),
                "scanned_at": service.catalog.scanned_at()}
    except _MS_ERRORS as exc:
        raise _ms_http_error(exc) from exc


@app.get("/api/v1/multispectral/map")
def multispectral_map(request: Request, response: Response,
                      authorization: str | None = Header(default=None)) -> dict:
    """Capture positions, nadir footprints / view cones and cached NDVI summaries."""
    service = _ms_service(request, authorization)
    _no_cache(response)
    try:
        return service.map_items()
    except _MS_ERRORS as exc:
        raise _ms_http_error(exc) from exc


@app.get("/api/v1/multispectral/captures/{capture_uuid}/layers/{layer}")
def multispectral_layer(capture_uuid: str, layer: str, request: Request, response: Response,
                        scale: int = Query(default=2, ge=1, le=4),
                        authorization: str | None = Header(default=None)) -> dict:
    service = _ms_service(request, authorization)
    if layer not in LAYERS:
        raise HTTPException(status_code=404, detail="Unknown layer")
    _no_cache(response)
    try:
        return service.analysis(capture_uuid, layer, scale=scale)
    except _MS_ERRORS as exc:
        raise _ms_http_error(exc) from exc


@app.get("/api/v1/multispectral/captures/{capture_uuid}/stack.tif")
def multispectral_stack(capture_uuid: str, request: Request,
                        product: str = Query(default="reflectance", pattern="^(reflectance|dn)$"),
                        scale: int = Query(default=1, ge=1, le=4),
                        refine: bool = Query(default=True), georef: bool = Query(default=True),
                        authorization: str | None = Header(default=None)) -> Response:
    """4-band GeoTIFF for QGIS (band order NIR, Green, Red, RedEdge)."""
    service = _ms_service(request, authorization)
    if scale not in (1, 2, 4):
        raise HTTPException(status_code=422, detail="scale must be 1, 2 or 4")
    try:
        data, info = service.stack_geotiff(capture_uuid, product=product, scale=scale,
                                           refine=refine, georef=georef)
    except _MS_ERRORS as exc:
        raise _ms_http_error(exc) from exc
    name = f"m3m_{info['capture_uuid'][:8]}_{product}_aligned.tif"
    shifts = ";".join(f"{b}:{s['dy_px']},{s['dx_px']}{'' if s['applied'] else '(n/a)'}"
                      for b, s in info["shifts"].items())
    return Response(content=data, media_type="image/tiff", headers={
        "Content-Disposition": f'attachment; filename="{name}"',
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer", "X-M3M-Residual-Shifts": shifts or "not computed"})


@app.get("/api/v1/multispectral/captures/{capture_uuid}/layers/{layer}/grid")
def multispectral_grid(capture_uuid: str, layer: str, request: Request,
                       scale: int = Query(default=2, ge=1, le=4),
                       authorization: str | None = Header(default=None)) -> Response:
    """Row-major float32 little-endian grid (NaN = outside sensor / invalid)."""
    service = _ms_service(request, authorization)
    if layer not in LAYERS:
        raise HTTPException(status_code=404, detail="Unknown layer")
    try:
        _, grid = service.layer(capture_uuid, layer, scale=scale)
    except _MS_ERRORS as exc:
        raise _ms_http_error(exc) from exc
    return Response(content=grid.astype("<f4").tobytes(), media_type="application/octet-stream",
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                             "Referrer-Policy": "no-referrer",
                             "X-Grid-Width": str(grid.shape[1]), "X-Grid-Height": str(grid.shape[0])})


class MetashapePackageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capture_uuids: list[str] = Field(min_length=3, max_length=100)
    mode: str = Field(default="rgb", pattern="^(rgb|multispectral)$")


@app.get("/api/v1/multispectral/metashape/packages")
def metashape_packages(request: Request, response: Response,
                       authorization: str | None = Header(default=None)) -> dict:
    service = _ms_service(request, authorization)
    _no_cache(response)
    try:
        return {"packages": list_packages(service), "execution": "external_worker"}
    except (OSError, WorkspaceError) as exc:
        raise HTTPException(503, "Private export workspace unavailable") from exc


@app.post("/api/v1/multispectral/metashape/packages", status_code=201)
def metashape_prepare_package(body: MetashapePackageRequest, request: Request, response: Response,
                              authorization: str | None = Header(default=None)) -> dict:
    service = _ms_service(request, authorization)
    _no_cache(response)
    try:
        return prepare_package(service, body.capture_uuids, body.mode)
    except MetashapeExportBusy as exc:
        raise HTTPException(503, str(exc), headers={"Retry-After": "10"}) from exc
    except MetashapeExportError as exc:
        raise HTTPException(422, str(exc)) from exc
    except _MS_ERRORS as exc:
        raise _ms_http_error(exc) from exc
    except WorkspaceError as exc:
        raise HTTPException(503, "Private export workspace unavailable") from exc


@app.get("/api/v1/multispectral/metashape/packages/{job_id}/file")
def metashape_download_package(job_id: str, request: Request,
                               authorization: str | None = Header(default=None)):
    service = _ms_service(request, authorization)
    try:
        path = package_path(service, job_id)
    except MetashapePackageNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except (OSError, WorkspaceError) as exc:
        raise HTTPException(503, "Private export workspace unavailable") from exc
    return FileResponse(path, media_type="application/zip", filename=f"aeronexus-metashape-{job_id}.zip",
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                                 "Referrer-Policy": "no-referrer"})


@app.delete("/api/v1/multispectral/metashape/packages/{job_id}", status_code=204)
def metashape_delete_package(job_id: str, request: Request,
                             authorization: str | None = Header(default=None)) -> None:
    service = _ms_service(request, authorization)
    try:
        remove_package(service, job_id)
    except MetashapePackageNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except (OSError, WorkspaceError) as exc:
        raise HTTPException(503, "Private export workspace unavailable") from exc


@app.post("/api/v1/flight/command", status_code=403)
def blocked_flight_command() -> None:
    raise HTTPException(status_code=403, detail="Flight commands disabled by default")

