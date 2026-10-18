"""DJI M4T/RC Plus 2 state-vs-OSD telemetry conformance regression tests."""
import importlib.util
import json
from pathlib import Path

import pytest

from aeronexus.cloud_api_details import normalize_details, validate_details
from aeronexus.cloud_api_mqtt import CloudMqttFeed, CloudOsdIngest, MqttSettings
from aeronexus.providers import ProviderKind
from aeronexus.status_runtime import StatusRuntime


def push(ingest, serial, channel, data, *, allow_state=True):
    return ingest.handle(
        f"thing/product/{serial}/{channel}",
        json.dumps({"data": data}).encode("utf-8"),
        allow_state=allow_state,
    )


def test_distance_limit_is_read_only_normalized_and_validated():
    raw = {"distance_limit_status": {"state": 1, "distance_limit": 200},
           "device_secret": "must-not-appear"}
    data = normalize_details("aircraft", raw)
    assert data == {"distance_limit": {"state_code": 1, "distance_limit_m": 200}}
    assert validate_details(data) == data
    assert "must-not-appear" not in json.dumps(data)


@pytest.mark.parametrize("value", [14, 8001, 18.5, True, "x"])
def test_distance_limit_out_of_range_rejected(value):
    with pytest.raises(ValueError):
        normalize_details("aircraft", {"distance_limit_status": {
            "state": 1, "distance_limit": value}})


def test_state_requires_device_osd_and_tracks_channel_metrics_without_serial():
    ingest = CloudOsdIngest(StatusRuntime())
    assert not push(ingest, "PRIVATEAIRCRAFT", "state", {"firmware_version": "1.2"})
    assert push(ingest, "PRIVATEAIRCRAFT", "osd", {
        "mode_code": 3, "distance_limit_status": {"state": 1, "distance_limit": 500}})
    assert push(ingest, "PRIVATEAIRCRAFT", "state", {
        "firmware_version": "1.2", "control_source": "A"})
    assert not push(ingest, "PRIVATEAIRCRAFT", "state", {
        "distance_limit_status": {"state": 1, "distance_limit": 10}})
    # The invalid state update is atomic and cannot erase the known OSD limit.
    record = ingest.runtime.inventory.telemetry(
        ProviderKind.CLOUD_API, "aeronexus", "PRIVATEAIRCRAFT")
    assert record.cloud_details["distance_limit"]["distance_limit_m"] == 500
    assert record.cloud_details["control_source_category"] == "controller_a"
    settings = MqttSettings(host="127.0.0.1", port=1884,
                            username="read-only-test", password="SECRET",
                            include_state=True)
    metrics = CloudMqttFeed(settings, ingest).status()
    assert metrics["channels"]["osd"]["accepted"] == 1
    assert metrics["channels"]["state"]["accepted"] == 1
    assert metrics["channels"]["state"]["ignored"] == 1
    assert metrics["channels"]["state"]["rejected"] == 1
    assert metrics["channels"]["state"]["last_message_at"] is not None
    assert "PRIVATEAIRCRAFT" not in json.dumps(metrics)
    assert "SECRET" not in json.dumps(metrics)


def test_state_disabled_does_not_update_data_and_is_counted_as_rejected():
    ingest = CloudOsdIngest(StatusRuntime())
    assert push(ingest, "TESTRC", "osd", {"capacity_percent": 70})
    assert not push(ingest, "TESTRC", "state", {"firmware_version": "1.2"},
                    allow_state=False)
    assert ingest.channel_counters["state"]["rejected"] == 1
    assert ingest.channel_counters["state"]["accepted"] == 0


def probe_module():
    path = Path(__file__).resolve().parents[1] / "scripts/pi/dji_state_conformance.py"
    spec = importlib.util.spec_from_file_location("dji_state_conformance", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_probe_only_exposes_fixed_property_paths_not_device_identity_or_values():
    mod = probe_module()
    captured = mod.empty_capture()
    secret = "VERY_PRIVATE_SERIAL_AND_LOCATION"
    snapshot = [{"provider": "dji-cloud-api", "kind": "aircraft",
                 "device_id": secret, "telemetry": {"latitude": 49.5},
                 "field_status": {
                     "flight_mode_code": {"channel": "osd"},
                     "cloud_details.firmware_version": {"channel": "state"},
                     secret: {"channel": "state"}}}]
    assert mod.accumulate(captured, snapshot) == {"aircraft": 1, "controller": 0}
    result = mod.report(captured, {"aircraft": 1, "controller": 1}, {
        "live_feed": {"state": "subscribed", "state_topic_enabled": True,
                      "channels": {"state": {"accepted": 1}, "osd": {"accepted": 2}}}})
    raw = json.dumps(result)
    assert "flight_mode_code" in raw
    assert "cloud_details.firmware_version" in raw
    assert secret not in raw
    assert "49.5" not in raw
    assert result["outcome"] == "state_events_observed_partial_property_evidence"


def test_probe_cannot_claim_state_coverage_from_osd_or_zero_events():
    mod = probe_module()
    capture = mod.empty_capture()
    mod.accumulate(capture, [{
        "provider": "dji-cloud-api", "kind": "controller",
        "field_status": {"cloud_details.firmware_version": {"channel": "osd"}},
    }])
    assert not capture["controller"]["state"]
    result = mod.report(capture, {"aircraft": 1, "controller": 1},
                        {"live_feed": {"state_topic_enabled": True,
                                       "channels": {"state": {"accepted": 0}}}})
    assert result["outcome"] == "state_event_not_observed"
    with pytest.raises(ValueError):
        mod.origin("http://127.0.0.1:8000")
    with pytest.raises(ValueError):
        mod.origin("https://example.com/?token=private")
