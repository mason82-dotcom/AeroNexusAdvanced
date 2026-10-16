"""Read-only API gateway with an authenticated fleet-status view.

DJI flight operations are not exposed. Detailed telemetry is inaccessible
unless an independent dashboard bearer token is configured.
"""
import asyncio
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote
from contextlib import asynccontextmanager
import os
import time
from enum import Enum
from secrets import compare_digest

from fastapi import FastAPI, Header, HTTPException, Query, Response, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse, StreamingResponse
from pydantic import BaseModel

from .cloud_api_mqtt import CloudMqttFeed, CloudOsdIngest, MqttSettings
from .flighthub_catalog import read_task_track
from .flighthub_poller import FlightHubFleetRefresher, FlightHubPollSettings
from .providers import ProviderKind
from .status_page import render_page
from .studio_page import render_studio
from .operations_page import render_operations
from .studio_workspace import Workspace, WorkspaceError, MAX_MEDIA_BYTES, MEDIA_TYPES
from .lan_access import lan_mode_enabled, require_lan
from .wpml_export import WaypointMission, export_kmz, import_kmz
from .status_polling import ReadOnlyStatusPoller
from .status_runtime import StatusRuntime, StatusSettings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start read-only data sources only when explicitly enabled."""
    settings = MqttSettings.from_env()
    poll_settings = FlightHubPollSettings.from_env()
    feed = None
    poll_task = None
    app.state.flighthub = None
    app.state.track_cache = {}
    stop_polling = asyncio.Event()
    if settings is not None:
        runtime = app.state.status_runtime
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
    return [ProviderStatus(provider=provider) for provider in Provider]


@app.get("/api/v1/providers/{provider}/status", response_model=ProviderStatus)
def provider_status(provider: Provider) -> ProviderStatus:
    return ProviderStatus(provider=provider)


@app.get("/api/v1/status/summary")
async def status_summary(response: Response) -> dict:
    """Only anonymous aggregate counts; never device IDs or GPS positions."""
    _no_cache(response)
    return app.state.status_runtime.summary()


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
        "img-src 'self' data: blob: https://tile.openstreetmap.org "
        "https://server.arcgisonline.com; "
        "connect-src 'self' https://tile.openstreetmap.org https://server.arcgisonline.com; "
        "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    )
    return render_operations()


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
        "img-src 'self' blob: data: https://tile.openstreetmap.org "
        "https://server.arcgisonline.com; "
        "connect-src 'self' https://tile.openstreetmap.org https://server.arcgisonline.com; "
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



@app.post("/api/v1/flight/command", status_code=403)
def blocked_flight_command() -> None:
    raise HTTPException(status_code=403, detail="Flight commands disabled by default")
