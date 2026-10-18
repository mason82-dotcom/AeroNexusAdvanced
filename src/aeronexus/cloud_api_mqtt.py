"""Opt-in, read-only DJI Cloud API live feed over MQTT (OSD and optional state).

Connects to the AeroNexus EMQX broker with a dedicated, ACL-restricted
account (subscribe thing/product/+/osd, optionally +/state, never publish) and
feeds strictly mapped telemetry into the local in-memory inventory. This module never
publishes MQTT messages; the client's publish method is disabled.

paho-mqtt is an optional dependency (extra "mqtt"), imported only on start.
"""
import asyncio
from dataclasses import dataclass
from datetime import datetime
import ipaddress
import os
import secrets
import re

from .hms_catalog import normalize_cloud_hms_event

from .cloud_api_osd import (CloudOsdError, OSD_TOPIC, STATE_TOPIC, MAX_PAYLOAD_BYTES,
                            classify, normalize_osd, osd_envelope, topic_device)
from .cloud_api_freshness import merge_fields
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
HMS_EVENT_TOPIC = "thing/product/+/events"
_HMS_EVENT = re.compile(r"thing/product/([A-Za-z0-9_-]{1,80})/events\Z")


@dataclass(frozen=True, repr=False)
class MqttSettings:
    host: str
    port: int
    username: str
    password: str
    tls: bool = False
    project_id: str = "aeronexus"
    max_devices: int = 50
    include_state: bool = False
    include_hms: bool = False

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
        if type(self.include_state) is not bool or type(self.include_hms) is not bool:
            raise ValueError("include_state and include_hms must be boolean")

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
        state_setting = env.get("AERONEXUS_OSD_STATE_ENABLED", "0").strip().lower()
        hms_setting = env.get("AERONEXUS_OSD_HMS_ENABLED", "0").strip().lower()
        if state_setting not in (*_TRUE, "0", "false", "no", "off", ""):
            raise ValueError("AERONEXUS_OSD_STATE_ENABLED must be 0 or 1")
        if hms_setting not in (*_TRUE, "0", "false", "no", "off", ""):
            raise ValueError("AERONEXUS_OSD_HMS_ENABLED must be 0 or 1")
        return cls(host=host, port=port, tls=tls,
                   include_hms=hms_setting in _TRUE,
                   include_state=state_setting in _TRUE,
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
        self.outdated = 0
        self.last_message_at: datetime | None = None
        self.hms_accepted = 0
        self.hms_rejected = 0
        self.hms_ignored = 0
        runtime.inventory.add_project(Project(CLOUD, project_id, "AeroNexus (DJI Cloud API)"))

    def handle(self, topic: str, payload: bytes, allow_state: bool = False) -> bool:
        inventory = self.runtime.inventory
        try:
            serial, channel = topic_device(topic)
            if channel == "state" and not allow_state:
                raise CloudOsdError("DJI state topic is not enabled")
            data, timestamp = osd_envelope(payload)
            received = utc_now()
            if timestamp is not None and timestamp > int(received.timestamp() * 1000) + 30000:
                raise CloudOsdError("DJI source clock too far in future")
            classified = classify(data)
            known = inventory._devices.get((CLOUD, self.project_id, serial))
            if channel == "state":
                # A state-only packet cannot establish the kind or prove a fresh
                # aircraft OSD sample. Only augment previously seen devices.
                if known is None:
                    self.ignored += 1
                    return False
                kind = known.kind
                if classified is not None and classified != kind:
                    raise CloudOsdError("State device type conflicts with known device")
            else:
                kind = classified if classified is not None else (known.kind if known else None)
                if kind is None:
                    self.ignored += 1
                    return False
                if known is not None and kind != known.kind:
                    raise CloudOsdError("OSD device type conflicts with known device")
            if known is None and len(inventory.devices(CLOUD, self.project_id)) >= self.max_devices:
                raise CloudOsdError("Device limit reached")
            fields = normalize_osd(kind, data)
            if not fields:
                self.ignored += 1
                return False
            previous = inventory.telemetry(CLOUD, self.project_id, serial)
            base = {} if previous is None else {
                key: value for key, value in vars(previous).items()
                if key not in ("provider", "device_id")}
            key = (CLOUD, self.project_id, serial)
            clocks = self.runtime.cloud_field_clocks.get(key, {})
            merged, staged, changed = merge_fields(base, fields, clocks, received, timestamp, channel)
            if not changed:
                self.ignored += 1
                self.outdated += 1
                return False
            osd_clock = self.runtime.cloud_osd_clocks.get(key)
            renew_osd = channel == 'osd' and (
                osd_clock is None or (timestamp is not None and (
                    osd_clock['source_timestamp_ms'] is None or timestamp > osd_clock['source_timestamp_ms']))
                or (timestamp is None and osd_clock['source_timestamp_ms'] is None))
            if renew_osd:
                merged['online'] = True
                staged['online'] = {'received_at': received, 'source_timestamp_ms': timestamp, 'channel': channel}
            record = {**merged, "device_id": serial}
            ingest_project_batch(
                inventory, CLOUD, self.project_id,
                [{"kind": kind.value, "device_id": serial, "name": _NAMES[kind]}],
                [record])
            self.runtime.cloud_field_clocks[key] = staged
            if renew_osd:
                self.runtime.cloud_osd_clocks[key] = staged['online']
            # State or late disjoint properties do not renew device liveness.
            inventory._received_at[key] = (received if renew_osd else
                                          osd_clock['received_at'] if osd_clock else received)
        except ValueError:
            # Covers CloudOsdError and all validation errors; content is not logged.
            self.rejected += 1
            return False
        self.accepted += 1
        self.last_message_at = utc_now()
        return True


    def handle_hms(self, topic: str, payload: bytes) -> bool:
        """Read full HMS snapshots for *already known* MQTT devices only.

        DJI documents HMS events as complete alarm lists: an empty list clears
        resolved warnings. No OSD liveness is renewed by HMS-only packets.
        A gateway event is not assigned to a different aircraft by guesswork.
        """
        match = _HMS_EVENT.fullmatch(topic) if isinstance(topic, str) else None
        if match is None:
            self.hms_rejected += 1
            return False
        key = (CLOUD, self.project_id, match.group(1))
        device = self.runtime.inventory._devices.get(key)
        if device is None:
            self.hms_ignored += 1
            return False
        try:
            alerts, timestamp = normalize_cloud_hms_event(payload, kind=device.kind.value)
            now = utc_now()
            if timestamp is not None and timestamp > int(now.timestamp() * 1000) + 30000:
                raise ValueError("HMS timestamp from future")
            previous = self.runtime.cloud_hms_clocks.get(key)
            if previous is not None:
                if timestamp is None and previous is not None:
                    # Undated packets cannot supersede an accepted dated snapshot.
                    self.hms_ignored += 1
                    return False
                if timestamp is not None and timestamp <= previous:
                    self.hms_ignored += 1
                    return False
            # Gateway /events reports dock/aircraft alarms together.
            # The record is grouped by *reporting* gateway, not assigned
            # by guesswork to an aircraft. Retain per-row device domain.
            previous_alerts = self.runtime.health.get(key)
            self.runtime.health[key] = alerts
            self.runtime.cloud_hms_clocks[key] = timestamp
            # Record changes only AFTER accepting the complete snapshot.
            # Storage errors are isolated from live telemetry by HmsHistory.
            self.runtime.hms_history.record_snapshot(
                key, previous_alerts, alerts, now, timestamp)
        except ValueError:
            self.hms_rejected += 1
            return False
        self.hms_accepted += 1
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
        subscriptions = [OSD_TOPIC]
        if self.settings.include_state:
            subscriptions.append(STATE_TOPIC)
        if self.settings.include_hms:
            subscriptions.append(HMS_EVENT_TOPIC)
        topics = ([(topic, 0) for topic in subscriptions]
                  if len(subscriptions) > 1 else OSD_TOPIC)
        result = client.subscribe(topics, qos=0)
        if isinstance(result, tuple) and len(result) >= 2 and result[0] == 0:
            self._pending_mid = result[1]
        else:
            self.state = "subscription_denied"

    def on_subscribe(self, client, userdata, mid, reason_codes, properties=None):
        if self._pending_mid is None or mid != self._pending_mid:
            return
        self._pending_mid = None
        expected = 1 + int(self.settings.include_state) + int(self.settings.include_hms)
        granted = (len(reason_codes) == expected and
                   all(_code(code) in (0, 1, 2) for code in reason_codes))
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
            if self.settings.include_hms and _HMS_EVENT.fullmatch(message.topic):
                self._loop.call_soon_threadsafe(
                    self.ingest.handle_hms, message.topic, bytes(payload))
            else:
                self._loop.call_soon_threadsafe(
                    self.ingest.handle, message.topic, bytes(payload), self.settings.include_state)
        except RuntimeError:
            pass  # event loop closed during shutdown

    def status(self) -> dict:
        """Anonymous counters only."""
        return {
            "source": "dji-cloud-api-mqtt",
            "state": self.state,
            "state_topic_enabled": self.settings.include_state,
            "hms_topic_enabled": self.settings.include_hms,
            "hms_accepted": self.ingest.hms_accepted,
            "hms_rejected": self.ingest.hms_rejected,
            "hms_ignored": self.ingest.hms_ignored,
            "accepted": self.ingest.accepted,
            "rejected": self.ingest.rejected,
            "ignored": self.ingest.ignored,
            "outdated": self.ingest.outdated,
            "last_message_at": utc_iso(self.ingest.last_message_at),
        }
