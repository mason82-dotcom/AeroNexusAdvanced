"""Matrice 4 series: offline read-only MQTT property contract tests.

DJI primary reference:
https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/pilot-to-cloud/mqtt/m4-series/properties.html#device-property-list

These are synthetic, allowlisted M4T snapshots. Passing is NOT a claim that
all M4 firmware properties, DJI Pilot 2, or a real flight were validated.
"""
import json
import time

import pytest

from aeronexus.cloud_api_details import validate_details
from aeronexus.cloud_api_mqtt import CloudOsdIngest
from aeronexus.cloud_api_osd import normalize_osd
from aeronexus.inventory import DeviceType
from aeronexus.providers import ProviderKind
from aeronexus.status_runtime import StatusRuntime


SN = "SYNTHETIC_MATRICE4T"
PROJECT = "aeronexus"
OSD = f"thing/product/{SN}/osd"
STATE = f"thing/product/{SN}/state"
KEY = (ProviderKind.CLOUD_API, PROJECT, SN)


def packet(data, timestamp=None):
    return json.dumps({
        "tid": "synthetic-transaction",
        "bid": "synthetic-business",
        "gateway": "SYNTHETIC_RC_PLUS2",
        "timestamp": int(time.time() * 1000) if timestamp is None else timestamp,
        "data": data,
    }).encode("utf-8")


def test_m4t_osd_flight_navigation_camera_battery_and_limits():
    raw = {
        "mode_code": 3,
        "latitude": 49.1,
        "longitude": 8.5,
        "height": 32.1,
        "horizontal_speed": 6.5,
        "vertical_speed": -0.3,
        "position_state": {
            "gps_number": 18, "rtk_number": 25,
            "is_fixed": 0, "quality": 10,
        },
        "battery": {
            "capacity_percent": 77,
            "remain_flight_time": 1200,
            "batteries": [{"index": 0, "voltage": 17000, "temperature": 31}],
        },
        "wind_speed": 52,
        "wind_direction": 1,
        "attitude_head": -12,
        "attitude_roll": 1.5,
        "attitude_pitch": -3,
        "distance_limit_status": {
            "state": 1, "distance_limit": 800,
            "is_near_distance_limit": 0,
        },
        "obstacle_avoidance": {"horizon": 1, "upside": 0, "downside": 1},
        "cameras": [{
            "payload_index": "89-0-0",
            "camera_mode": 0,
            "photo_storage_settings": ["current", "vision", "ir"],
        }],
        "89-0-0": {"gimbal_pitch": -45, "gimbal_roll": 1, "gimbal_yaw": 5},
        "device_secret": "MUST_NOT_APPEAR",
        "nonce": "MUST_NOT_APPEAR",
    }
    sample = normalize_osd(DeviceType.AIRCRAFT, raw)
    details = sample["cloud_details"]
    assert sample["flight_mode_code"] == 3
    assert sample["horizontal_speed_mps"] == 6.5
    assert sample["vertical_speed_mps"] == -0.3
    assert sample["battery_percent"] == 77
    assert sample["rtk_state"] == "is_fixed:0"
    assert details["position"]["quality_code"] == 10
    assert details["wind_speed_mps"] == pytest.approx(5.2)
    assert details["distance_limit"] == {
        "state_code": 1, "distance_limit_m": 800, "near_limit": False,
    }
    assert details["obstacle_avoidance"] == {
        "horizon_enabled": True, "upside_enabled": False,
        "downside_enabled": True,
    }
    assert details["aircraft_model_hint"] == "M4T"
    assert details["cameras"][0]["photo_storage_settings"] == [
        "current", "vision", "ir",
    ]
    assert details["payloads"]["89-0-0"]["gimbal_pitch_deg"] == -45
    assert validate_details(details) == details
    assert "MUST_NOT_APPEAR" not in json.dumps(sample)


def test_m4t_state_rth_firmware_and_control_source_preserve_osd_liveness():
    ingest = CloudOsdIngest(StatusRuntime())
    t = int(time.time() * 1000) - 1000
    assert ingest.handle(OSD, packet({
        "mode_code": 3, "battery": {"capacity_percent": 75},
    }, t))
    old_sample = ingest.runtime.inventory.telemetry(*KEY)
    old_osd_clock = dict(ingest.runtime.cloud_osd_clocks[KEY])
    old_battery_clock = dict(
        ingest.runtime.cloud_field_clocks[KEY]["battery_percent"])
    assert ingest.handle(STATE, packet({
        "current_rth_mode": 1,
        "rth_mode": 0,
        "rth_altitude": 80,
        "control_source": "B",
        "firmware_version": "01.00.00.00",
        "low_battery_warning_threshold": 25,
    }, t + 5), allow_state=True)

    updated = ingest.runtime.inventory.telemetry(*KEY)
    details = updated.cloud_details
    assert details["current_rth_mode_code"] == 1
    assert details["rth_mode_code"] == 0
    assert details["rth_altitude_m"] == 80
    assert details["control_source_category"] == "controller_b"
    assert details["firmware_version"] == "01.00.00.00"
    assert details["low_battery_warning_percent"] == 25
    assert updated.battery_percent == old_sample.battery_percent
    assert ingest.runtime.cloud_osd_clocks[KEY] == old_osd_clock
    assert ingest.runtime.cloud_field_clocks[KEY]["battery_percent"] == old_battery_clock
    for path in (
        "cloud_details.current_rth_mode_code",
        "cloud_details.rth_mode_code",
        "cloud_details.rth_altitude_m",
        "cloud_details.control_source_category",
    ):
        assert ingest.runtime.cloud_field_clocks[KEY][path]["channel"] == "state"


@pytest.mark.parametrize("invalid", [
    {"rth_altitude": 19},
    {"rth_altitude": 501},
    {"current_rth_mode": True},
    {"distance_limit_status": {"distance_limit": 10}},
    {"distance_limit_status": {"state": 2}},
])
def test_m4_invalid_properties_fail_atomically(invalid):
    ingest = CloudOsdIngest(StatusRuntime())
    assert ingest.handle(OSD, packet({"mode_code": 3, "height": 20}))
    sample = ingest.runtime.inventory.telemetry(*KEY)
    osd_clock = dict(ingest.runtime.cloud_osd_clocks[KEY])
    clocks = dict(ingest.runtime.cloud_field_clocks[KEY])
    assert not ingest.handle(STATE, packet(invalid), allow_state=True)
    assert ingest.rejected == 1
    assert ingest.runtime.inventory.telemetry(*KEY) == sample
    assert ingest.runtime.cloud_osd_clocks[KEY] == osd_clock
    assert ingest.runtime.cloud_field_clocks[KEY] == clocks


def test_m4t_payload_control_keeps_only_category_not_serial_or_browser_uuid():
    uuid = "12345678-1234-1234-1234-123456789abc"
    details = normalize_osd(DeviceType.AIRCRAFT, {
        "mode_code": 3,
        "payloads": [{
            "payload_index": "89-0-0",
            "control_source": uuid,
            "firmware_version": "01.00.00.00",
            "sn": "PRIVATE_PAYLOAD_SN",
        }],
    })["cloud_details"]
    assert details["aircraft_model_hint"] == "M4T"
    assert details["payload_control"][0]["control_source_category"] == "browser"
    assert details["payload_control"][0]["firmware_version"] == "01.00.00.00"
    assert uuid not in json.dumps(details)
    assert "PRIVATE_PAYLOAD_SN" not in json.dumps(details)
    assert validate_details(details) == details
