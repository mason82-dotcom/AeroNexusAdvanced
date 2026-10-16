"""Opt-in, read-only DJI Cloud API live feed over MQTT (OSD subscription only).

Connects to the AeroNexus EMQX broker with a dedicated, ACL-restricted
account (subscribe thing/product/+/osd, never publish) and feeds validated
OSD telemetry into the local in-memory inventory. This module never
publishes MQTT messages; the client's publish method is disabled.

paho-mqtt is an optional dependency (extra "mqtt"), imported only on start.
"""
import asyncio
from dataclasses import dataclass
from datetime import datetime
import ipaddress
import os
import secrets

from .cloud_api_osd import (CloudOsdError, OSD_TOPIC, MAX_PAYLOAD_BYTES, classify,
                            normalize_osd, osd_data, topic_serial)
from .inventory import DeviceType, Project
from .providers import ProviderKind
from .status_runtime import StatusRuntime, utc_iso, utc_now
from .sync_pipeline import ingest_project_batch


CLOUD = ProviderKind.CLOUD_API
_NAMES = {DeviceType.AIRCRAFT: "Aircraft", DeviceType.CONTROLLER: "Remote controller"}
# Accounts that can publish or that belong to other consumers.
_FORBIDDEN_USERS = frozenset({"companion", "admin", "dashboard", "onprem-backend",
                              "pilot", "pilot2", "backend"})
_TRUE = ("1", "true", "yes", "on")


@dataclass(frozen=True, repr=False)
class MqttSettings:
    host: str
    port: int
    username: str
    password: str
    tls: bool = False
    project_id: str = "aeronexus"
    max_devices: int = 50

    def __post_init__(self):
        if not self.host or any(ch.isspace() for ch in self.host) or "/" in self.host:
            raise ValueError("Invalid MQTT broker host")
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("MQTT broker port out of range")
        if (not self.username or any(ch.isspace() for ch in self.username)
                or self.username in _FORBIDDEN_USERS):
            raise ValueError("A dedicated read-only OSD account is required")
        if not self.password:
            raise ValueError("MQTT password required")
        if not self.project_id.strip():
            raise ValueError("Project ID required")
        if type(self.max_devices) is not int or not 1 <= self.max_devices <= 500:
            raise ValueError("max_devices must be 1..500")

    def __repr__(self):
        return (f"MqttSettings(host={self.host!r}, port={self.port}, "
                f"username={self.username!r}, password='<redacted>', tls={self.tls})")

    @classmethod
    def from_env(cls, environ=None) -> "MqttSettings | None":
        """None unless AERONEXUS_CLOUD_MQTT_ENABLED is set; invalid config raises."""
        env = os.environ if environ is None else environ
        if env.get("AERONEXUS_CLOUD_MQTT_ENABLED", "").strip().lower() not in _TRUE:
            return None
        host = env.get("AERONEXUS_OSD_HOST", "127.0.0.1")
        tls = env.get("AERONEXUS_OSD_TLS", "").strip().lower() in _TRUE
        if not tls and not _is_loopback(host) and env.get(
                "AERONEXUS_OSD_ALLOW_PLAINTEXT_LAN", "").strip().lower() not in _TRUE:
            raise ValueError("Plaintext MQTT to a non-loopback broker needs "
                             "AERONEXUS_OSD_ALLOW_PLAINTEXT_LAN=1 or AERONEXUS_OSD_TLS=1")
        try:
            port = int(env.get("AERONEXUS_OSD_PORT", "1884"))
        except ValueError as exc:
            raise ValueError("Invalid MQTT broker port") from exc
        return cls(host=host, port=port, tls=tls,
                   username=env.get("AERONEXUS_OSD_USERNAME", ""),
                   password=env.get("AERONEXUS_OSD_PASSWORD", ""),
                   project_id=env.get("AERONEXUS_CLOUD_PROJECT_ID", "aeronexus"))


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class CloudOsdIngest:
    """Applies OSD messages to the inventory; must run on the event loop thread."""

    def __init__(self, runtime: StatusRuntime, project_id: str = "aeronexus",
                 max_devices: int = 50):
        if not isinstance(runtime, StatusRuntime):
            raise TypeError("StatusRuntime required")
        self.runtime = runtime
        self.project_id = project_id
        self.max_devices = max_devices
        self.accepted = 0
        self.rejected = 0
        self.ignored = 0
        self.last_message_at: datetime | None = None
        runtime.inventory.add_project(Project(CLOUD, project_id, "AeroNexus (DJI Cloud API)"))

    def handle(self, topic: str, payload: bytes) -> bool:
        inventory = self.runtime.inventory
        try:
            serial = topic_serial(topic)
            data = osd_data(payload)
            kind = classify(data)
            if kind is None:
                self.ignored += 1
                return False
            known = inventory._devices.get((CLOUD, self.project_id, serial))
            if known is None and len(inventory.devices(CLOUD, self.project_id)) >= self.max_devices:
                raise CloudOsdError("Device limit reached")
            fields = normalize_osd(kind, data)
            previous = inventory.telemetry(CLOUD, self.project_id, serial)
            base = {} if previous is None else {
                key: value for key, value in vars(previous).items()
                if key not in ("provider", "device_id")}
            record = {**base, **fields, "device_id": serial, "online": True}
            ingest_project_batch(
                inventory, CLOUD, self.project_id,
                [{"kind": kind.value, "device_id": serial, "name": _NAMES[kind]}],
                [record])
        except ValueError:
            # Covers CloudOsdError and all validation errors; content is not logged.
            self.rejected += 1
            return False
        self.accepted += 1
        self.last_message_at = utc_now()
        return True


def _code(reason_code) -> int:
    return int(getattr(reason_code, "value", reason_code))


def _forbidden_publish(*args, **kwargs):
    raise PermissionError("AeroNexusAdvanced MQTT feed is read-only")


class CloudMqttFeed:
    """paho-mqtt network thread -> asyncio loop -> CloudOsdIngest."""

    def __init__(self, settings: MqttSettings, ingest: CloudOsdIngest, client_factory=None):
        self.settings = settings
        self.ingest = ingest
        self._client_factory = client_factory
        self._client = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._pending_mid = None
        self.state = "stopped"

    def _make_client(self):
        if self._client_factory is not None:
            return self._client_factory()
        import paho.mqtt.client as mqtt
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                           client_id="aeronexusadvanced-osd-" + secrets.token_hex(4),
                           clean_session=True)

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        client = self._make_client()
        client.publish = _forbidden_publish
        client.username_pw_set(self.settings.username, self.settings.password)
        if self.settings.tls:
            client.tls_set()  # system CAs, certificate verification enabled
        client.reconnect_delay_set(min_delay=1, max_delay=30)
        client.on_connect = self.on_connect
        client.on_subscribe = self.on_subscribe
        client.on_disconnect = self.on_disconnect
        client.on_connect_fail = self.on_connect_fail
        client.on_message = self.on_message
        self._client = client
        self.state = "connecting"
        client.connect_async(self.settings.host, self.settings.port, keepalive=30)
        client.loop_start()

    def stop(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            client.disconnect()
            client.loop_stop()
        self.state = "stopped"

    # paho callbacks (network thread)
    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        self._pending_mid = None
        if _code(reason_code) != 0:
            self.state = "auth_failed"
            return
        self.state = "connected"
        result = client.subscribe(OSD_TOPIC, qos=0)
        if isinstance(result, tuple) and len(result) >= 2 and result[0] == 0:
            self._pending_mid = result[1]

    def on_subscribe(self, client, userdata, mid, reason_codes, properties=None):
        if self._pending_mid is None or mid != self._pending_mid:
            return
        self._pending_mid = None
        granted = len(reason_codes) == 1 and _code(reason_codes[0]) in (0, 1, 2)
        self.state = "subscribed" if granted else "subscription_denied"

    def on_connect_fail(self, client, userdata):
        # TCP/TLS connection failed; paho keeps retrying in its network loop.
        self.state = "unreachable"

    def on_disconnect(self, client, userdata, *args):
        self._pending_mid = None
        if self.state != "stopped":
            self.state = "disconnected"

    def on_message(self, client, userdata, message):
        if self.state != "subscribed" or self._loop is None:
            return
        payload = message.payload
        if not isinstance(payload, (bytes, bytearray)) or len(payload) > MAX_PAYLOAD_BYTES:
            return
        try:
            self._loop.call_soon_threadsafe(self.ingest.handle, message.topic, bytes(payload))
        except RuntimeError:
            pass  # event loop closed during shutdown

    def status(self) -> dict:
        """Anonymous counters only."""
        return {
            "source": "dji-cloud-api-mqtt",
            "state": self.state,
            "accepted": self.ingest.accepted,
            "rejected": self.ingest.rejected,
            "ignored": self.ingest.ignored,
            "last_message_at": utc_iso(self.ingest.last_message_at),
        }
