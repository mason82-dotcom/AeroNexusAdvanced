"""DJI Cloud API OSD normalization and validated, atomic ingestion."""
import json

import pytest

from aeronexus.cloud_api_mqtt import CloudOsdIngest
from aeronexus.cloud_api_osd import (CloudOsdError, classify, normalize_osd, osd_data,
                                     topic_serial)
from aeronexus.inventory import DeviceType
from aeronexus.providers import ProviderKind
from aeronexus.status_runtime import StatusRuntime


CLOUD = ProviderKind.CLOUD_API
DRONE = "1581F8HGX000TEST"
RC = "9N9CN000RCTEST"

# Shape of a Pilot 2 aircraft OSD push (DJI Cloud API, Matrice 4 series).
AIRCRAFT = {
    "mode_code": 3, "latitude": 49.1, "longitude": 8.5, "height": 162.4,
    "elevation": 42.3, "home_distance": 120.0, "horizontal_speed": 5.2,
    "vertical_speed": -0.4, "total_flight_time": 36000, "total_flight_sorties": 57,
    "position_state": {"gps_number": 21, "rtk_number": 30, "is_fixed": 2, "quality": 5},
    "battery": {"capacity_percent": 76, "remain_flight_time": 1200,
                "batteries": [{"capacity_percent": 76, "voltage": 16420, "temperature": 31.5}]},
    "cameras": [{"payload_index": "99-0-0"}],
}
CONTROLLER = {"capacity_percent": 88, "latitude": 49.1, "longitude": 8.5,
              "wireless_link": {"sdr_quality": 5}}


def envelope(data):
    return json.dumps({"tid": "t", "bid": "b", "timestamp": 1, "data": data}).encode()


def topic(sn):
    return f"thing/product/{sn}/osd"


def test_topic_serial_strict():
    assert topic_serial(topic(DRONE)) == DRONE
    for bad in ("thing/product/a/b/osd", "thing/product//osd", "sys/product/x/osd",
                "thing/product/x/osd/extra", "thing/product/../osd", None):
        with pytest.raises(CloudOsdError):
            topic_serial(bad)


def test_osd_data_bounded_and_object_only():
    assert osd_data(envelope({"a": 1})) == {"a": 1}
    for bad in (b"", b"x" * 70000, b"\xff", b"[]", envelope({}), envelope([1]),
                json.dumps({"data": None}).encode()):
        with pytest.raises(CloudOsdError):
            osd_data(bad)


def test_classification():
    assert classify(AIRCRAFT) == DeviceType.AIRCRAFT
    assert classify(CONTROLLER) == DeviceType.CONTROLLER
    assert classify({"battery": {"capacity_percent": 3}}) == DeviceType.AIRCRAFT
    assert classify({"cameras": []}) is None
    assert classify({"latitude": 1, "longitude": 2}) is None


def test_aircraft_mapping():
    f = normalize_osd(DeviceType.AIRCRAFT, AIRCRAFT)
    assert f == {
        "latitude": 49.1, "longitude": 8.5, "height_m": 162.4, "elevation_m": 42.3,
        "home_distance_m": 120.0, "horizontal_speed_mps": 5.2, "vertical_speed_mps": -0.4,
        "total_flight_time_s": 36000, "total_flight_sorties": 57, "flight_mode_code": 3,
        "gps_satellites": 21, "rtk_satellites": 30, "rtk_state": "is_fixed:2",
        "battery_percent": 76, "battery_voltage_mv": 16420, "battery_temperature_c": 31.5,
    }


def test_controller_mapping_ignores_aircraft_fields():
    assert normalize_osd(DeviceType.CONTROLLER, CONTROLLER) == {
        "latitude": 49.1, "longitude": 8.5, "battery_percent": 88}


def test_zero_position_is_no_location_and_strings_accepted():
    f = normalize_osd(DeviceType.AIRCRAFT, {"latitude": 0, "longitude": 0.0,
                                            "elevation": "12.5", "mode_code": "0"})
    assert f["latitude"] is None and f["longitude"] is None
    assert f["elevation_m"] == 12.5 and f["flight_mode_code"] == 0


@pytest.mark.parametrize("data", [
    {"mode_code": True}, {"mode_code": 1.5}, {"elevation": "nan"}, {"elevation": [1]},
    {"position_state": "x"}, {"battery": 5}, {"elevation": "1e999"},
])
def test_invalid_values_rejected(data):
    with pytest.raises(CloudOsdError):
        normalize_osd(DeviceType.AIRCRAFT, data)


@pytest.fixture
def ingest():
    return CloudOsdIngest(StatusRuntime(), "aeronexus", max_devices=3)


def test_ingest_registers_aircraft_and_controller(ingest):
    assert ingest.handle(topic(DRONE), envelope(AIRCRAFT))
    assert ingest.handle(topic(RC), envelope(CONTROLLER))
    inv = ingest.runtime.inventory
    kinds = {d.device_id: d.kind for d in inv.devices(CLOUD, "aeronexus")}
    assert kinds == {DRONE: DeviceType.AIRCRAFT, RC: DeviceType.CONTROLLER}
    snap = inv.telemetry(CLOUD, "aeronexus", DRONE)
    assert snap.online is True and snap.battery_percent == 76 and snap.elevation_m == 42.3
    views = {v["device_id"]: v for v in ingest.runtime.device_views()}
    assert views[DRONE]["freshness"] == "fresh" and views[DRONE]["online"] is True
    assert ingest.accepted == 2 and ingest.rejected == 0


def test_partial_push_keeps_previous_values(ingest):
    ingest.handle(topic(DRONE), envelope(AIRCRAFT))
    assert ingest.handle(topic(DRONE), envelope({"mode_code": 9, "elevation": 60}))
    snap = ingest.runtime.inventory.telemetry(CLOUD, "aeronexus", DRONE)
    assert snap.flight_mode_code == 9 and snap.elevation_m == 60
    assert snap.battery_percent == 76 and snap.gps_satellites == 21


def test_invalid_message_does_not_change_state(ingest):
    ingest.handle(topic(DRONE), envelope(AIRCRAFT))
    before = ingest.runtime.inventory.telemetry(CLOUD, "aeronexus", DRONE)
    assert not ingest.handle(topic(DRONE), envelope({**AIRCRAFT, "battery": {"capacity_percent": 150}}))
    assert not ingest.handle(topic(DRONE), envelope({"latitude": 91, "longitude": 8, "mode_code": 1}))
    assert ingest.runtime.inventory.telemetry(CLOUD, "aeronexus", DRONE) == before
    assert ingest.rejected == 2


def test_type_change_rejected(ingest):
    ingest.handle(topic(DRONE), envelope(AIRCRAFT))
    assert not ingest.handle(topic(DRONE), envelope(CONTROLLER))
    assert ingest.runtime.inventory.devices()[0].kind == DeviceType.AIRCRAFT


def test_unclassified_ignored_and_device_limit(ingest):
    assert not ingest.handle(topic(DRONE), envelope({"cameras": []}))
    assert ingest.ignored == 1 and not ingest.runtime.inventory.devices()
    for i in range(3):
        assert ingest.handle(topic(f"SN{i}"), envelope(CONTROLLER))
    assert not ingest.handle(topic("SN9"), envelope(CONTROLLER))
    assert ingest.handle(topic("SN0"), envelope(CONTROLLER))  # known devices continue
    assert len(ingest.runtime.inventory.devices()) == 3


def test_bad_topic_and_payload_rejected(ingest):
    assert not ingest.handle("thing/product/x/state", envelope(AIRCRAFT))
    assert not ingest.handle(topic(DRONE), b"not json")
    assert ingest.rejected == 2
