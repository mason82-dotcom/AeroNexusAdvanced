"""Read-only fleet status projections with explicit telemetry freshness.

Time stamps are local receive times in UTC, NOT source/event times at DJI.
No background network activity or flight controls in this module.
"""
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from .inventory import DeviceType, Inventory
from .providers import ProviderKind
from .cloud_api_freshness import clock_view, project_fields
from .hms_history import HmsHistory


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class StatusSettings:
    stale_after_seconds: int = 90
    refresh_every_seconds: int = 30

    def __post_init__(self):
        if type(self.stale_after_seconds) is not int or not 5 <= self.stale_after_seconds <= 86400:
            raise ValueError("stale_after_seconds must be 5..86400")
        if type(self.refresh_every_seconds) is not int or not 5 <= self.refresh_every_seconds <= 3600:
            raise ValueError("refresh_every_seconds must be 5..3600")


@dataclass
class StatusRuntime:
    inventory: Inventory = field(default_factory=Inventory)
    settings: StatusSettings = field(default_factory=StatusSettings)
    # Filled by a future explicitly configured read-only provider poller.
    polling: str = "disabled"
    last_refresh_at: datetime | None = None
    last_refresh_success_at: datetime | None = None
    # Anonymous counters of an opt-in push feed (DJI Cloud API MQTT), if any.
    live_feed: Callable[[], dict] | None = None
    # Live FlightHub HMS alerts per (provider, project, device); None = not read.
    health: dict[tuple[ProviderKind, str, str], tuple[dict, ...]] = field(default_factory=dict)
    # Bounded HMS state-transition log; disk persistence is configured at startup.
    hms_history: HmsHistory = field(default_factory=HmsHistory)
    # FlightHub project library (waylines, models, tasks) per (provider, project).
    catalog: dict[tuple[ProviderKind, str], dict] = field(default_factory=dict)
    flighthub_system_ok: bool | None = None
    catalog_updated_at: datetime | None = None
    cloud_field_clocks: dict = field(default_factory=dict, repr=False)
    cloud_osd_clocks: dict = field(default_factory=dict, repr=False)
    cloud_hms_clocks: dict = field(default_factory=dict, repr=False)

    def device_views(
        self, provider: ProviderKind | None = None,
        project_id: str | None = None, *, now: datetime | None = None,
    ) -> tuple[dict, ...]:
        now = utc_now() if now is None else now
        utc_iso(now)
        views = []
        for device in self.inventory.devices(provider, project_id):
            snapshot = self.inventory.telemetry(device.provider, device.project_id, device.device_id)
            received = self.inventory.telemetry_received_at(
                device.provider, device.project_id, device.device_id)
            age = None
            if snapshot is None:
                freshness = "missing"
            elif received is None:
                freshness = "unknown_age"
            else:
                # Future receive times indicate clock skew, not fresh telemetry.
                delta = (now - received).total_seconds()
                if delta < -1:
                    freshness = "clock_skew"
                else:
                    age = round(max(0.0, delta), 3)
                    freshness = "fresh" if delta <= self.settings.stale_after_seconds else "stale"
            sample = ({} if snapshot is None else {
                key: value for key, value in asdict(snapshot).items()
                if key not in ("provider", "device_id")
            })
            cloud = {}
            key = (device.provider, device.project_id, device.device_id)
            clocks = self.cloud_field_clocks.get(key)
            if clocks:
                last_known = sample
                sample, field_status = project_fields(sample, clocks, now, self.settings.stale_after_seconds)
                cloud = {'field_status': field_status, 'last_known_telemetry': last_known}
                osd_clock = self.cloud_osd_clocks.get(key)
                if osd_clock:
                    freshness = clock_view(osd_clock, now, self.settings.stale_after_seconds)['freshness']
            views.append({
                "provider": device.provider.value,
                "project_id": device.project_id,
                "device_id": device.device_id,
                "kind": device.kind.value,
                "name": ((snapshot.cloud_details or {}).get('aircraft_model_hint', device.name)
                         if device.name == 'Aircraft' and snapshot is not None else device.name),
                "freshness": freshness,
                "received_at": utc_iso(received),
                "age_seconds": age,
                "online": sample.get('online') if snapshot is not None and freshness == "fresh" else None,
                "reported_online": None if snapshot is None else snapshot.online,
                "telemetry": sample,
                "health": list(self.health.get(
                    (device.provider, device.project_id, device.device_id), ())),
                "hms_history": self.hms_history.list_events(
                    provider=device.provider.value, project_id=device.project_id,
                    device_id=device.device_id, limit=12)["events"],
                **cloud,
            })
        return tuple(views)

    def summary(self, *, now: datetime | None = None) -> dict:
        now = utc_now() if now is None else now
        views = self.device_views(now=now)
        freshness = ("fresh", "stale", "missing", "unknown_age", "clock_skew")
        return {
            "server_time": utc_iso(now),
            "registered_devices": len(views),
            "aircraft": sum(v["kind"] == DeviceType.AIRCRAFT.value for v in views),
            "controllers": sum(v["kind"] == DeviceType.CONTROLLER.value for v in views),
            **{status: sum(v["freshness"] == status for v in views) for status in freshness},
            "online_fresh": sum(v["online"] is True for v in views),
            "offline_fresh": sum(v["online"] is False for v in views),
            "stale_after_seconds": self.settings.stale_after_seconds,
            "refresh_every_seconds": self.settings.refresh_every_seconds,
            "polling": self.polling,
            "last_refresh_at": utc_iso(self.last_refresh_at),
            "last_refresh_success_at": utc_iso(self.last_refresh_success_at),
            "live_feed": {"state": "disabled"} if self.live_feed is None else self.live_feed(),
            "health_warnings": sum(any(a.get("level") == "warning" for a in v["health"])
                                   for v in views),
            "hms_history_events": len(self.hms_history.events),
            "hms_history_persistent": (self.hms_history.path is not None
                                       and not self.hms_history.storage_error),
            "hms_history_storage_error": self.hms_history.storage_error,
            "flighthub": {
                "system_status": {None: "unknown", True: "ok", False: "error"}[self.flighthub_system_ok],
                "catalog_updated_at": utc_iso(self.catalog_updated_at),
                **{key: sum(len(c.get(key) or []) for c in self.catalog.values())
                   for key in ("waylines", "models", "tasks")},
            },
        }
