"""Opt-in periodic FlightHub 2 V2 fleet refresh for the status dashboard.

Read-only: project list GET, then per selected project the fleet GETs of
flighthub_fleet. Disabled unless AERONEXUS_FH_POLL_ENABLED is set.

Environment:
  AERONEXUS_FH_POLL_ENABLED       1 to enable
  AERONEXUS_DJI_PROVIDER          public | onprem
  AERONEXUS_DJI_REGION            public: eu (default) | us | cn
  AERONEXUS_DJI_BASE_URL          HTTPS origin; overrides the region, required for onprem
  AERONEXUS_DJI_API_VERSION       public: v2.0 (default) | v0.1
  AERONEXUS_DJI_TOKEN             organization key (X-User-Token / x-user-token)
  AERONEXUS_DJI_ORGANIZATION_UUID required for On-Premises (project list path)
  AERONEXUS_DJI_PROJECT_UUIDS     optional comma list; default: all listed projects
  AERONEXUS_DJI_ORGANIZATION_ID   public, optional: organization short code (e.g. shown
                                  in FlightHub); checks that the key belongs to it
  AERONEXUS_FH_POLL_SECONDS       10..3600, default 30
  AERONEXUS_FH_CATALOG_SECONDS    public library refresh (waylines, models, tasks,
                                  system status): 0 = off, 60..86400, default 600
"""
from collections.abc import Mapping
from dataclasses import dataclass
import os
import re
import time
from uuid import UUID

from .flighthub_catalog import read_catalog, read_system_status
from .flighthub_fleet import sync_project_fleet
from .flighthub_hms import read_public_hms
from .live_project_sync import read_project_page
from .providers import REGIONS, ProviderConfig, ProviderKind
from .read_only_transport import ReadOnlyTransport
from .status_runtime import StatusRuntime, utc_now


_TRUE = ("1", "true", "yes", "on")
_PROVIDERS = {"public": ProviderKind.PUBLIC_V2, "onprem": ProviderKind.ONPREM_V2}
MAX_PROJECTS = 10
_SHORT_CODE = re.compile(r"[A-Za-z0-9]{4,32}\Z")


@dataclass(frozen=True, repr=False)
class FlightHubPollSettings:
    config: ProviderConfig
    organization_uuid: str | None
    project_uuids: tuple[str, ...]
    interval_seconds: int = 30
    organization_code: str | None = None
    catalog_interval_seconds: int = 600

    def __post_init__(self):
        if self.config.kind not in (ProviderKind.PUBLIC_V2, ProviderKind.ONPREM_V2):
            raise ValueError("FlightHub V2 provider required")
        if self.config.kind == ProviderKind.ONPREM_V2 and not self.organization_uuid:
            raise ValueError("AERONEXUS_DJI_ORGANIZATION_UUID required for On-Premises")
        if type(self.interval_seconds) is not int or not 10 <= self.interval_seconds <= 3600:
            raise ValueError("AERONEXUS_FH_POLL_SECONDS must be 10..3600")
        if (type(self.catalog_interval_seconds) is not int or not (
                self.catalog_interval_seconds == 0 or 60 <= self.catalog_interval_seconds <= 86400)):
            raise ValueError("AERONEXUS_FH_CATALOG_SECONDS must be 0 or 60..86400")
        if len(self.project_uuids) > MAX_PROJECTS:
            raise ValueError("Too many projects selected")
        if self.organization_code is not None and (
                self.config.kind != ProviderKind.PUBLIC_V2
                or _SHORT_CODE.fullmatch(self.organization_code) is None):
            raise ValueError("AERONEXUS_DJI_ORGANIZATION_ID must be a Public Cloud short code")

    def __repr__(self):
        return (f"FlightHubPollSettings(config={self.config!r}, "
                f"projects={len(self.project_uuids) or 'all'}, interval={self.interval_seconds})")

    @classmethod
    def from_env(cls, environ=None) -> "FlightHubPollSettings | None":
        env = os.environ if environ is None else environ
        if env.get("AERONEXUS_FH_POLL_ENABLED", "").strip().lower() not in _TRUE:
            return None
        kind = _PROVIDERS.get(env.get("AERONEXUS_DJI_PROVIDER", "").strip().lower())
        if kind is None:
            raise ValueError("AERONEXUS_DJI_PROVIDER must be public or onprem")
        base_url = env.get("AERONEXUS_DJI_BASE_URL", "").strip()
        if not base_url and kind == ProviderKind.PUBLIC_V2:
            region = env.get("AERONEXUS_DJI_REGION", "eu").strip().lower()
            if region not in REGIONS:
                raise ValueError("AERONEXUS_DJI_REGION must be eu, us or cn")
            base_url = REGIONS[region]
        config = ProviderConfig(kind, base_url, env.get("AERONEXUS_DJI_TOKEN", ""),
                                env.get("AERONEXUS_DJI_API_VERSION", "v2.0").strip() or "v2.0")
        projects = tuple(_uuid(item) for item in
                         env.get("AERONEXUS_DJI_PROJECT_UUIDS", "").split(",") if item.strip())
        org = env.get("AERONEXUS_DJI_ORGANIZATION_UUID", "").strip() or None
        try:
            interval = int(env.get("AERONEXUS_FH_POLL_SECONDS", "30"))
        except ValueError as exc:
            raise ValueError("AERONEXUS_FH_POLL_SECONDS must be an integer") from exc
        code = env.get("AERONEXUS_DJI_ORGANIZATION_ID", "").strip() or None
        try:
            catalog = int(env.get("AERONEXUS_FH_CATALOG_SECONDS", "600"))
        except ValueError as exc:
            raise ValueError("AERONEXUS_FH_CATALOG_SECONDS must be an integer") from exc
        return cls(config, _uuid(org) if org else None, projects, interval, code, catalog)


def _uuid(value: str) -> str:
    try:
        return str(UUID(value.strip()))
    except (ValueError, AttributeError) as exc:
        raise ValueError("Invalid UUID in FlightHub configuration") from exc


class FlightHubFleetRefresher:
    """Async callable for ReadOnlyStatusPoller."""

    def __init__(self, runtime: StatusRuntime, settings: FlightHubPollSettings):
        self.runtime = runtime
        self.settings = settings
        self.projects_synced = 0
        self.devices_synced = 0
        self.hms_ok: bool | None = None
        self.organization_verified = False
        self._catalog_due = 0.0

    async def _verify_organization(self) -> None:
        """Once per process: the key must see the configured organization."""
        config = self.settings.config
        path = config.path("/organizations")
        payload = await ReadOnlyTransport(config, frozenset({path})).get(
            path, {"page": 1, "page_size": 100})
        data = payload.get("data")
        rows = data.get("list") if isinstance(data, Mapping) else None
        codes = {row.get("organization_id") for row in rows or [] if isinstance(row, Mapping)}
        if self.settings.organization_code.upper() not in {
                c.upper() for c in codes if isinstance(c, str)}:
            raise ValueError("Organization key does not belong to the configured organization")
        self.organization_verified = True

    async def __call__(self) -> None:
        inventory = self.runtime.inventory
        if self.settings.organization_code and not self.organization_verified:
            await self._verify_organization()
        projects = await read_project_page(
            self.settings.config, organization_uuid=self.settings.organization_uuid,
            page=1, page_size=100)
        wanted = set(self.settings.project_uuids)
        selected = [p for p in projects if not wanted or p.project_id in wanted][:MAX_PROJECTS]
        if wanted and len(selected) != len(wanted):
            raise ValueError("Configured project not visible to the organization key")
        devices = 0
        hms_results = []
        for project in selected:
            known = inventory._projects.get((project.provider, project.project_id))
            if known is None or known == project:
                inventory.add_project(project)
            else:  # renamed in FlightHub
                inventory._projects[(project.provider, project.project_id)] = project
            device_count, _ = await sync_project_fleet(
                inventory, self.settings.config, project.project_id)
            devices += device_count
            hms_results.append(await self._refresh_health(project.provider, project.project_id))
        self.projects_synced, self.devices_synced = len(selected), devices
        known = [r for r in hms_results if r is not None]
        self.hms_ok = all(known) if known else None
        await self._refresh_catalog(selected)

    async def _refresh_catalog(self, projects) -> None:
        """Library changes rarely: refreshed on its own, slower interval."""
        settings = self.settings
        if (settings.config.kind != ProviderKind.PUBLIC_V2 or not settings.catalog_interval_seconds
                or not projects or time.monotonic() < self._catalog_due):
            return
        self._catalog_due = time.monotonic() + settings.catalog_interval_seconds
        try:
            self.runtime.flighthub_system_ok = await read_system_status(
                settings.config, projects[0].project_id)
        except (ValueError, RuntimeError):
            self.runtime.flighthub_system_ok = False
        catalog = {}
        for project in projects:
            catalog[(project.provider, project.project_id)] = await read_catalog(
                settings.config, project.project_id)
        self.runtime.catalog = catalog
        self.runtime.catalog_updated_at = utc_now()

    async def _refresh_health(self, provider: ProviderKind, project_id: str) -> bool | None:
        """HMS is best effort: a failure keeps telemetry and drops stale alerts."""
        if provider != ProviderKind.PUBLIC_V2:
            return None  # On-Premises HMS is organization-scoped; not wired yet
        sns = [d.device_id for d in self.runtime.inventory.devices(provider, project_id)]
        keys = [(provider, project_id, sn) for sn in sns]
        try:
            alerts = await read_public_hms(self.settings.config, project_id, sns) if sns else {}
        except (ValueError, RuntimeError):
            for key in keys:
                self.runtime.health.pop(key, None)
            return False
        for key in keys:
            self.runtime.health[key] = alerts.get(key[2], ())
        return True
