"""Read-only MQTT feed: configuration, subscribe-only behaviour, app wiring."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from aeronexus import app as app_module
from aeronexus.cloud_api_mqtt import CloudMqttFeed, CloudOsdIngest, MqttSettings
from aeronexus.status_runtime import StatusRuntime


ENV = {"AERONEXUS_CLOUD_MQTT_ENABLED": "1", "AERONEXUS_OSD_USERNAME": "aeronexus_osd",
       "AERONEXUS_OSD_PASSWORD": "secret-osd-password"}


class FakeClient:
    def __init__(self):
        self.calls = []
        self.published = []

    def publish(self, *args, **kwargs):  # replaced by the feed
        self.published.append(args)

    def username_pw_set(self, user, password):
        self.calls.append(("auth", user))

    def tls_set(self):
        self.calls.append(("tls",))

    def reconnect_delay_set(self, **kwargs):
        pass

    def connect_async(self, host, port, keepalive):
        self.calls.append(("connect", host, port))

    def loop_start(self):
        self.calls.append(("loop_start",))

    def loop_stop(self):
        self.calls.append(("loop_stop",))

    def disconnect(self):
        self.calls.append(("disconnect",))

    def subscribe(self, topic, qos):
        self.calls.append(("subscribe", topic, qos))
        return (0, 7)


def test_disabled_by_default():
    assert MqttSettings.from_env({}) is None
    assert MqttSettings.from_env({**ENV, "AERONEXUS_CLOUD_MQTT_ENABLED": "0"}) is None


def test_settings_from_env_and_redacted_repr():
    s = MqttSettings.from_env(ENV)
    assert (s.host, s.port, s.username, s.tls) == ("127.0.0.1", 1884, "aeronexus_osd", False)
    assert "secret-osd-password" not in repr(s)


@pytest.mark.parametrize("override", [
    {"AERONEXUS_OSD_USERNAME": ""}, {"AERONEXUS_OSD_USERNAME": "companion"},
    {"AERONEXUS_OSD_USERNAME": "pilot2"}, {"AERONEXUS_OSD_USERNAME": "onprem-backend"},
    {"AERONEXUS_OSD_PASSWORD": ""}, {"AERONEXUS_OSD_PORT": "0"}, {"AERONEXUS_OSD_PORT": "x"},
    {"AERONEXUS_OSD_HOST": "192.168.1.5"}, {"AERONEXUS_OSD_HOST": "a b"},
])
def test_invalid_settings_fail_closed(override):
    with pytest.raises(ValueError):
        MqttSettings.from_env({**ENV, **override})


def test_lan_broker_needs_explicit_plaintext_opt_in_or_tls():
    lan = {**ENV, "AERONEXUS_OSD_HOST": "192.168.1.5"}
    assert MqttSettings.from_env({**lan, "AERONEXUS_OSD_ALLOW_PLAINTEXT_LAN": "1"}).host == "192.168.1.5"
    assert MqttSettings.from_env({**lan, "AERONEXUS_OSD_TLS": "1"}).tls is True


def make_feed(loop=None):
    fake = FakeClient()
    ingest = CloudOsdIngest(StatusRuntime())
    feed = CloudMqttFeed(MqttSettings.from_env(ENV), ingest, client_factory=lambda: fake)
    feed.start(loop or asyncio.new_event_loop())
    return feed, fake


def test_start_subscribes_only_osd_and_never_publishes():
    feed, fake = make_feed()
    assert ("auth", "aeronexus_osd") in fake.calls and ("connect", "127.0.0.1", 1884) in fake.calls
    assert feed.state == "connecting"
    with pytest.raises(PermissionError):
        fake.publish("thing/product/x/services", b"{}")
    feed.on_connect(fake, None, {}, 0)
    assert ("subscribe", "thing/product/+/osd", 0) in fake.calls
    assert [c for c in fake.calls if c[0] == "subscribe"] == [("subscribe", "thing/product/+/osd", 0)]
    feed.on_subscribe(fake, None, 7, [0])
    assert feed.state == "subscribed"
    feed.stop()
    assert ("disconnect",) in fake.calls and feed.state == "stopped"
    assert fake.published == []


def test_auth_failure_and_denied_subscription():
    feed, fake = make_feed()
    feed.on_connect(fake, None, {}, SimpleNamespace(value=135))
    assert feed.state == "auth_failed"
    feed.on_connect(fake, None, {}, 0)
    feed.on_subscribe(fake, None, 99, [0])  # foreign mid ignored
    assert feed.state == "connected"
    feed.on_subscribe(fake, None, 7, [SimpleNamespace(value=0x87)])
    assert feed.state == "subscription_denied"


def test_messages_ignored_until_subscribed_then_applied_on_loop():
    loop = asyncio.new_event_loop()
    feed, fake = make_feed(loop)
    msg = SimpleNamespace(topic="thing/product/RC1/osd",
                          payload=json.dumps({"data": {"capacity_percent": 50}}).encode())
    feed.on_message(fake, None, msg)
    feed.on_connect(fake, None, {}, 0)
    feed.on_subscribe(fake, None, 7, [0])
    feed.on_message(fake, None, msg)
    feed.on_message(fake, None, SimpleNamespace(topic=msg.topic, payload=b"x" * 70000))
    loop.call_soon(loop.stop)
    loop.run_forever()
    loop.close()
    status = feed.status()
    assert status["accepted"] == 1 and status["rejected"] == 0
    assert status["state"] == "subscribed" and status["last_message_at"].endswith("Z")
    assert "RC1" not in json.dumps(status)


def test_disconnect_marks_feed(monkeypatch):
    feed, fake = make_feed()
    feed.on_connect(fake, None, {}, 0)
    feed.on_subscribe(fake, None, 7, [0])
    feed.on_disconnect(fake, None, {}, 7)
    assert feed.state == "disconnected"
    feed.on_connect_fail(fake, None)
    assert feed.state == "unreachable"


def test_app_summary_reports_feed_state(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(app_module.app.state, "status_runtime", StatusRuntime())
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(app_module.CloudMqttFeed, "_make_client", lambda self: fake)
    with TestClient(app_module.app) as client:
        body = client.get("/api/v1/status/summary").json()
        assert body["live_feed"]["state"] == "connecting"
        assert "secret-osd-password" not in json.dumps(body)
    assert ("disconnect",) in fake.calls


def test_app_without_feed(monkeypatch):
    monkeypatch.setattr(app_module.app.state, "status_runtime", StatusRuntime())
    monkeypatch.delenv("AERONEXUS_CLOUD_MQTT_ENABLED", raising=False)
    with TestClient(app_module.app) as client:
        assert client.get("/api/v1/status/summary").json()["live_feed"] == {"state": "disabled"}


def test_state_subscription_is_explicit_and_requires_full_acl_grant():
    expanded = {**ENV, "AERONEXUS_OSD_STATE_ENABLED": "1"}
    settings = MqttSettings.from_env(expanded)
    assert settings.include_state is True
    assert "secret-osd-password" not in repr(settings)
    fake = FakeClient()
    feed = CloudMqttFeed(settings, CloudOsdIngest(StatusRuntime()),
                         client_factory=lambda: fake)
    loop = asyncio.new_event_loop()
    try:
        feed.start(loop)
        with pytest.raises(PermissionError):
            fake.publish("thing/product/SN/services", b"{}")
        feed.on_connect(fake, None, {}, 0)
        assert ("subscribe", [("thing/product/+/osd", 0),
                              ("thing/product/+/state", 0)], 0) in fake.calls
        feed.on_subscribe(fake, None, 7, [0, 0])
        assert feed.state == "subscribed"
        assert feed.status()["state_topic_enabled"] is True
        assert not fake.published
    finally:
        feed.stop()
        loop.close()


def test_state_acl_partial_grant_fails_closed():
    fake = FakeClient()
    settings = MqttSettings.from_env({**ENV, "AERONEXUS_OSD_STATE_ENABLED": "1"})
    feed = CloudMqttFeed(settings, CloudOsdIngest(StatusRuntime()),
                         client_factory=lambda: fake)
    loop = asyncio.new_event_loop()
    try:
        feed.start(loop)
        feed.on_connect(fake, None, {}, 0)
        feed.on_subscribe(fake, None, 7, [0, 0x87])
        assert feed.state == "subscription_denied"
        feed.on_message(fake, None, SimpleNamespace(
            topic="thing/product/SN/state",
            payload=json.dumps({"data": {"elevation": 99}}).encode()))
        assert feed.ingest.accepted == 0
    finally:
        feed.stop()
        loop.close()


def test_invalid_state_env_value_fails_closed():
    for raw in ("maybe", "enabled", "2", "true-but-not-really"):
        with pytest.raises(ValueError):
            MqttSettings.from_env({**ENV, "AERONEXUS_OSD_STATE_ENABLED": raw})
    assert MqttSettings.from_env(ENV).include_state is False


def test_state_mqtt_callback_updates_only_existing_device():
    settings = MqttSettings.from_env({**ENV, "AERONEXUS_OSD_STATE_ENABLED": "1"})
    fake = FakeClient()
    ingest = CloudOsdIngest(StatusRuntime())
    feed = CloudMqttFeed(settings, ingest, client_factory=lambda: fake)
    loop = asyncio.new_event_loop()
    try:
        feed.start(loop)
        feed.on_connect(fake, None, {}, 0)
        feed.on_subscribe(fake, None, 7, [0, 0])
        osd = SimpleNamespace(topic="thing/product/SN/osd",
                              payload=json.dumps({"data": {
                                  "mode_code": 3, "elevation": 10}}).encode())
        state = SimpleNamespace(topic="thing/product/SN/state",
                                payload=json.dumps({"data": {
                                    "elevation": 16, "device_secret": "private"}}).encode())
        feed.on_message(fake, None, osd)
        feed.on_message(fake, None, state)
        loop.call_soon(loop.stop)
        loop.run_forever()
        sample = ingest.runtime.inventory.telemetry(
            app_module.ProviderKind.CLOUD_API, settings.project_id, "SN")
        assert sample.elevation_m == 16 and sample.flight_mode_code == 3
        assert "private" not in repr(sample)
        assert feed.status()["accepted"] == 2
    finally:
        feed.stop()
        loop.close()
