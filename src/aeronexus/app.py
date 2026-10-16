"""Read-only API gateway with an authenticated fleet-status view.

DJI flight operations are not exposed. Detailed telemetry is inaccessible
unless an independent dashboard bearer token is configured.
"""
import os
from enum import Enum
from secrets import compare_digest

from fastapi import FastAPI, Header, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .providers import ProviderKind
from .status_page import render_page
from .status_runtime import StatusRuntime, StatusSettings


app = FastAPI(title="AeroNexusAdvanced", version="0.1.0")
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
    if len(configured) < 32:
        raise HTTPException(status_code=503, detail="Status detail authentication is not configured")
    if (not isinstance(authorization, str) or len(authorization) > 512
            or not authorization.startswith("Bearer ")
            or not compare_digest(authorization[7:], configured)):
        raise HTTPException(
            status_code=401, detail="Invalid status access credential",
            headers={"WWW-Authenticate": "Bearer"},
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
    response: Response,
    authorization: str | None = Header(default=None),
    provider: ProviderKind | None = None,
    project_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Authenticated details, bounded pagination, no external DJI fetch."""
    _no_cache(response)
    _require_dashboard_token(authorization)
    devices = app.state.status_runtime.device_views(provider, project_id)
    return {"total": len(devices), "offset": offset, "limit": limit,
            "devices": list(devices[offset:offset + limit])}


@app.get("/status", response_class=HTMLResponse)
async def status_page(response: Response) -> str:
    """Browser refreshes local status automatically; no DJI polling by default."""
    _no_cache(response)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; script-src 'unsafe-inline'; "
        "style-src 'unsafe-inline'; connect-src 'self'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
    )
    return render_page(app.state.status_runtime.settings.refresh_every_seconds)


@app.post("/api/v1/flight/command", status_code=403)
def blocked_flight_command() -> None:
    raise HTTPException(status_code=403, detail="Flight commands disabled by default")
