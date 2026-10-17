"""Health of the local DJI Cloud API stack (cloud-server/edge), read-only.

Probes only the published loopback ports of the Compose services and never
uses their credentials: AeroNexusAdvanced does not read cloud-server/.env.

* api      HTTP :6789  any answer below 500 means up (401 without login)
* control  HTTP :8085  Pilot 2 login page (/pilot-login)
* mqtt     TCP  :1884  EMQX accepts connections (no MQTT login attempted)
* minio    HTTP :9000  /minio/health/live
* mediamtx HTTP :9997  path list (loopback-only control API, no login)

Connected controllers and aircraft come from the inventory of the existing
read-only MQTT telemetry feed; no extra broker subscription is made.
"""
from __future__ import annotations

import asyncio
import ipaddress
import os
import time

import httpx

DEFAULT_HOST = "127.0.0.1"
TIMEOUT_S = 1.5
CACHE_S = 10.0
HTTP_PROBES = {
    "api": (6789, "/manage/api/v1/workspaces/current", "DJI Cloud API (Backend)"),
    "control": (8085, "/pilot-login", "Weboberfläche und Pilot-2-Login"),
    "minio": (9000, "/minio/health/live", "MinIO (Medienablage)"),
    "mediamtx": (9997, "/v3/paths/list", "MediaMTX (Livestream)"),
}
MQTT_PORT = 1884
ORDER = ("api", "mqtt", "minio", "control", "mediamtx")
LABELS = {**{k: v[2] for k, v in HTTP_PROBES.items()}, "mqtt": "EMQX (MQTT-Broker)"}


def stack_host(environ=None) -> str:
    env = os.environ if environ is None else environ
    host = env.get("AERONEXUS_CLOUD_STACK_HOST", DEFAULT_HOST).strip()
    try:
        if not ipaddress.ip_address(host).is_loopback:
            raise ValueError
    except ValueError:
        raise ValueError("AERONEXUS_CLOUD_STACK_HOST must be a loopback address") from None
    return host


async def _http(client: httpx.AsyncClient, host: str, name: str) -> dict:
    port, path, _ = HTTP_PROBES[name]
    started = time.monotonic()
    try:
        response = await client.get(f"http://{host}:{port}{path}")
    except httpx.HTTPError:
        return {"state": "down"}
    ms = round((time.monotonic() - started) * 1000)
    if response.status_code >= 500:
        return {"state": "error", "http": response.status_code, "ms": ms}
    result = {"state": "up", "http": response.status_code, "ms": ms}
    if name == "minio" and response.status_code != 200:
        result["state"] = "error"
    if name == "mediamtx":
        try:
            items = response.json().get("items") or []
            result["streams"] = sum(1 for i in items if isinstance(i, dict) and i.get("ready"))
        except (ValueError, AttributeError):
            result["state"] = "error"
    return result


async def _tcp(host: str, port: int) -> dict:
    started = time.monotonic()
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), TIMEOUT_S)
    except (OSError, asyncio.TimeoutError):
        return {"state": "down"}
    writer.close()
    try:
        await writer.wait_closed()
    except OSError:
        pass
    return {"state": "up", "ms": round((time.monotonic() - started) * 1000)}


class CloudStackHealth:
    def __init__(self, host: str | None = None, *, transport=None, tcp=None):
        self.host = host or stack_host()
        self._transport = transport
        self._tcp = tcp or _tcp
        self._cache: tuple[float, dict] | None = None
        self._lock = asyncio.Lock()

    async def services(self) -> dict:
        async with self._lock:
            if self._cache and time.monotonic() - self._cache[0] < CACHE_S:
                return self._cache[1]
            async with httpx.AsyncClient(timeout=TIMEOUT_S, follow_redirects=False,
                                         trust_env=False, transport=self._transport) as client:
                names = list(HTTP_PROBES)
                results = await asyncio.gather(
                    *(_http(client, self.host, n) for n in names),
                    self._tcp(self.host, MQTT_PORT))
            found = dict(zip(names + ["mqtt"], results))
            services = {n: {"label": LABELS[n], **found[n]} for n in ORDER}
            self._cache = (time.monotonic(), services)
            return services


def fleet_view(device_views, feed: dict | None) -> dict:
    """Cloud API devices of the read-only MQTT feed, names but no serials."""
    rows = []
    for view in device_views:
        if view.get("provider") != "dji-cloud-api":
            continue
        rows.append({"kind": view.get("kind"), "name": view.get("name"),
                     "online": view.get("online") is True and view.get("freshness") == "fresh",
                     "freshness": view.get("freshness"), "received_at": view.get("received_at")})
    rows.sort(key=lambda r: (r["kind"] != "controller", not r["online"], r["name"] or ""))
    feed = feed or {}
    return {"feed_state": feed.get("state", "disabled"),
            "last_message_at": feed.get("last_message_at"), "devices": rows}


def overall(services: dict, fleet: dict) -> str:
    core = ("api", "mqtt", "minio", "control")
    if any(services[n]["state"] != "up" for n in core):
        return "degraded"
    if fleet["feed_state"] not in ("subscribed", "disabled"):
        return "degraded"
    return "ok"
