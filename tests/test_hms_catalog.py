"""DJI Cloud API HMS copy-key, metadata and read-only MQTT lifecycle tests."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

from aeronexus.hms_catalog import (
    _read_catalog, normalize_code, resolve_hms, normalize_cloud_hms_event,
    severity, _render,
)
from aeronexus.flighthub_hms import normalize_hms
from aeronexus.cloud_api_mqtt import MqttSettings, CloudMqttFeed, CloudOsdIngest, HMS_EVENT_TOPIC
from aeronexus.providers import ProviderKind
from aeronexus.status_runtime import StatusRuntime


@pytest.fixture
def catalog(tmp_path, monkeypatch):
    p = tmp_path / "hms.json"
    p.write_text(json.dumps({
        "fpv_tip_0x16100083_in_the_sky": {
            "de": "Kamera %component_index: Sensor %index; Akku %battery_index; %alarmid",
            "en": "Camera %component_index"
        },
        "fpv_tip_0x16100083": {"de": "Prüfung am Boden"},
        "fpv_tip_0x16100084": {"en": "Camera module error"},
        "dock_tip_0x19110020": {
            "de": "Abdeckung %dock_cover_index; Stange %charging_rod_index",
            "en": "Dock %dock_cover_index"
        },
        "dock_tip_0x19110021": {"en": "Dock %1$s cover needs attention"},
    }), encoding="utf-8")
    monkeypatch.setenv("AERONEXUS_HMS_CATALOG_PATH", str(p))
    _read_catalog.cache_clear()
    yield p
    _read_catalog.cache_clear()


def test_exact_copy_keys_de_args_and_levels(catalog):
    msg = resolve_hms({"code": "0x16100083", "in_the_sky": 1,
                       "level": 2, "module": 3, "imminent": 1,
                       "args": {"component_index": 0, "sensor_index": 0}},
                      kind="aircraft")
    assert msg["message"] == (
        "Kamera 1: Sensor 1; Akku links; 0x16100083"
    )
    assert msg["level"] == "warning" and msg["module"] == "HMS"
    assert msg["imminent"] is True and msg["in_the_sky"] is True
    assert msg["message_source"] == "dji-hms-catalog-de"
    ground = resolve_hms({"code": "16100083", "in_the_sky": 0}, kind="aircraft")
    assert ground["message"] == "Prüfung am Boden"


def test_dock_copy_keys_and_german_index_replacements(catalog):
    item = {"code": "0x19110020", "args": {"sensor_index": 2},
            "level": 1, "module": 1}
    found = resolve_hms(item, kind="dock")
    assert found["message"] == "Abdeckung rechts; Stange links"
    assert found["level"] == "reminder"
    assert found["module"] == "Geräteverwaltung"
    assert resolve_hms({"code": "0x19110021",
                        "args": {"sensor_index": 0}}, kind="dock")["message"] == (
        "Dock links cover needs attention"
    )


def test_english_fallback_and_unknown_codes_never_invent_diagnostics(catalog):
    en = resolve_hms({"code": "0x16100084", "level": 0}, kind="aircraft")
    assert en["message"] == "Camera module error"
    assert en["message_source"] == "dji-hms-catalog-en"
    unknown = resolve_hms({"code": "0xDEADBEEF", "level": 2}, kind="aircraft")
    assert unknown["code"] == "0xDEADBEEF"
    assert unknown["message"] is None
    assert unknown["level"] == "warning"
    assert unknown["message_source"] == "unknown"
    gateway = resolve_hms({"code": "0x19110020"}, kind="controller")
    assert gateway["message"] is None  # cannot claim this is a dock alert
    assert resolve_hms({"code": "not hex", "message": "Originaltext"}, kind="aircraft")[
        "message"] == "Originaltext"


@pytest.mark.parametrize(("value", "expected"), [
    (0, "notification"), (1, "reminder"), (2, "warning"),
    ("2", "warning"), ("warning", "warning"), (7, "unknown"), (None, "unknown")
])
def test_levels(value, expected):
    assert severity(value) == expected


def test_invalid_catalog_or_unknown_fields_do_not_leak(tmp_path, monkeypatch):
    path = tmp_path / "catalog.json"
    monkeypatch.setenv("AERONEXUS_HMS_CATALOG_PATH", str(path))
    path.write_text("not JSON", encoding="utf-8")
    _read_catalog.cache_clear()
    assert resolve_hms({"code": "0x12040000"}, kind="dock")["message"] == "RTK-Gerät getrennt"
    path.write_text(json.dumps({"malicious_secret": {"de": "should never match"}}))
    _read_catalog.cache_clear()
    assert resolve_hms({"code": "0xAAAA0001"}, kind="dock")["message"] is None
    assert normalize_code("0xZZZZFFFF") is None
    assert normalize_code("0x" + "A" * 400) is None


def test_full_snapshot_mqtt_hms_event_and_empty_clear(catalog):
    runtime = StatusRuntime()
    ingest = CloudOsdIngest(runtime)
    assert ingest.handle("thing/product/AC01/osd",
                         json.dumps({"data": {"mode_code": 3, "elevation": 10}}).encode())
    before = runtime.inventory.telemetry_received_at(ProviderKind.CLOUD_API, "aeronexus", "AC01")
    first = {"method": "hms", "timestamp": 1792344000000,
             "data": {"list": [
                {"code": "0x16100083", "in_the_sky": 1, "level": 2, "module": 3,
                 "args": {"component_index": 0, "sensor_index": 0}}
             ]}}
    assert ingest.handle_hms("thing/product/AC01/events", json.dumps(first).encode())
    key = (ProviderKind.CLOUD_API, "aeronexus", "AC01")
    assert len(runtime.health[key]) == 1
    assert runtime.health[key][0]["message_source"] == "dji-hms-catalog-de"
    assert runtime.inventory.telemetry_received_at(*key) == before
    assert not ingest.handle_hms("thing/product/AC01/events", json.dumps(first).encode())
    second = {"method": "hms", "timestamp": first["timestamp"] + 1,
              "data": {"list": []}}
    assert ingest.handle_hms("thing/product/AC01/events", json.dumps(second).encode())
    assert runtime.health[key] == ()
    assert ingest.hms_accepted == 2 and ingest.hms_ignored == 1


def test_mqtt_hms_does_not_register_devices_or_update_on_invalid(catalog):
    ingest = CloudOsdIngest(StatusRuntime())
    valid = json.dumps({"method": "hms", "data": {"list": [
        {"code": "0x16100083", "level": 2, "module": 3}
    ]}}).encode()
    assert not ingest.handle_hms("thing/product/UNKNOWN/events", valid)
    assert ingest.hms_ignored == 1
    assert len(ingest.runtime.inventory.devices()) == 0
    for payload in (b"{}", b"{", b"x" * 65537,
                    json.dumps({"method": "osd", "data": {"list": []}}).encode(),
                    json.dumps({"method": "hms", "data": {"list": [
                        {"code": "x", "level": 2, "module": 3}]}}).encode()):
        with pytest.raises(ValueError):
            normalize_cloud_hms_event(payload)
    assert not ingest.handle_hms("sys/product/AC01/status", valid)


def test_flighthub_code_resolution_and_native_text_fallback(catalog):
    payload = {"code": 0, "data": {"list": [
        {"device_sn": "AC01", "device_hms": {"list": [
            {"code": "0x16100083", "level": "warning",
             "in_the_sky": "in_the_sky", "status": 1,
             "args": {"sensor_index": 0, "component_index": 0}},
            {"code": "private-code", "message": "FlightHub native", "status": 1,
             "level": "notification"},
            {"code": "0x16100084", "status": 0},
        ]}}
    ]}}
    normalized = normalize_hms(payload, ["AC01"])
    assert len(normalized["AC01"]) == 2
    assert normalized["AC01"][0]["message_source"] == "dji-hms-catalog-de"
    assert normalized["AC01"][1]["message"] == "FlightHub native"


def test_hms_mqtt_setting_opt_in_and_subscriptions():
    env = {"AERONEXUS_CLOUD_MQTT_ENABLED": "1", "AERONEXUS_OSD_USERNAME": "aeronexus_osd",
           "AERONEXUS_OSD_PASSWORD": "test-only"}
    assert MqttSettings.from_env(env).include_hms is False
    settings = MqttSettings.from_env({**env, "AERONEXUS_OSD_HMS_ENABLED": "1"})
    assert settings.include_hms
    assert HMS_EVENT_TOPIC == "thing/product/+/events"
    class Fake:
        calls = []
        def username_pw_set(self, *a): pass
        def reconnect_delay_set(self, **kw): pass
        def connect_async(self, *a, **kw): pass
        def loop_start(self): pass
        def disconnect(self): pass
        def loop_stop(self): pass
        def subscribe(self, topics, qos):
            self.calls.append(topics)
            return (0, 7)
    import asyncio
    loop = asyncio.new_event_loop()
    fake = Fake()
    feed = CloudMqttFeed(settings, CloudOsdIngest(StatusRuntime()),
                         client_factory=lambda: fake)
    try:
        feed.start(loop)
        with pytest.raises(PermissionError):
            fake.publish("any", b"x")
        feed.on_connect(fake, None, {}, 0)
        assert fake.calls == [[("thing/product/+/osd", 0),
                               ("thing/product/+/events", 0)]]
        feed.on_subscribe(fake, None, 7, [0, 0])
        assert feed.state == "subscribed"
        assert feed.status()["hms_topic_enabled"]
    finally:
        feed.stop()
        loop.close()
    with pytest.raises(ValueError):
        MqttSettings.from_env({**env, "AERONEXUS_OSD_HMS_ENABLED": "unexpected"})


def test_dji_device_type_domain_selects_the_correct_copy_key(catalog):
    # HMS is published by the gateway, but a single snapshot may contain
    # drone and dock entries, each with their own device_type domain.
    dock = resolve_hms({"code": "0x19110020", "device_type": "3-67-0",
                        "args": {"sensor_index": 0}}, kind="controller")
    assert dock["device_domain"] == "dock"
    assert dock["message"] == "Abdeckung links; Stange vorn"
    drone = resolve_hms({"code": "0x16100083", "device_type": "0-67-0",
                         "in_the_sky": 1}, kind="controller")
    assert drone["device_domain"] == "aircraft"
    assert drone["message"] is not None


def test_cloud_mqtt_allows_documented_methodless_hms_sample(catalog):
    msg = json.dumps({"timestamp": 1700000000000, "data": {"list": [
        {"code": "0x16100083", "device_type": "0-67-0", "level": 2,
         "module": 3, "in_the_sky": 0}
    ]}}).encode()
    rows, ts = normalize_cloud_hms_event(msg)
    assert ts == 1700000000000
    assert len(rows) == 1 and rows[0]["device_domain"] == "aircraft"


def test_methodless_empty_event_does_not_clear_active_alarms():
    with pytest.raises(ValueError):
        normalize_cloud_hms_event(b'{"data":{"list":[]}}')
    rows, timestamp = normalize_cloud_hms_event(
        b'{"method":"hms","timestamp":1700000000000,"data":{"list":[]}}')
    assert rows == () and timestamp == 1700000000000


def test_official_gateway_alarm_contains_device_origin_metadata(catalog):
    result = resolve_hms({"code": "0x16100083", "device_type": "0-67-0",
                          "in_the_sky": 1}, kind="controller")
    assert result["source"] == "dji-cloud-hms"
    assert result["device_domain"] == "aircraft"
    assert result["message_source"] == "dji-hms-catalog-de"
