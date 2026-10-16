"""WPML waypoint KMZ exports: structure, profiles and safe validation."""
from io import BytesIO
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import pytest
from pydantic import ValidationError

from aeronexus.wpml_export import Waypoint, WaypointMission, export_kmz, KML_NS, WPML_NS


W = f"{{{WPML_NS}}}"
K = f"{{{KML_NS}}}"


def draft(**changes):
    values = {
        "name": "Inspektion",
        "drone_model": "matrice4t",
        "altitude_m": 50.0,
        "speed_mps": 5.0,
        "takeoff_security_height_m": 20.0,
        "rth_height_m": 60.0,
        "finish_action": "goHome",
        "waypoints": [
            {"latitude": 49.1, "longitude": 8.5, "take_photo": True},
            {"latitude": 49.2, "longitude": 8.6, "take_photo": False},
        ],
    }
    values.update(changes)
    return WaypointMission.model_validate(values)


def files(mission):
    archive = ZipFile(BytesIO(export_kmz(mission, timestamp_ms=1760641200000)))
    assert sorted(archive.namelist()) == ["wpmz/template.kml", "wpmz/waylines.wpml"]
    return (
        ET.fromstring(archive.read("wpmz/template.kml")),
        ET.fromstring(archive.read("wpmz/waylines.wpml")),
    )


def test_kmz_contains_both_dji_wpml_documents():
    template, waylines = files(draft())
    assert template.tag == K + "kml"
    assert waylines.tag == K + "kml"
    assert template.find(".//" + W + "templateType").text == "waypoint"
    assert template.find(".//" + W + "templateId").text == "0"
    assert waylines.find(".//" + W + "templateId").text == "0"
    assert waylines.find(".//" + W + "waylineId").text == "0"
    assert template.find(".//" + W + "heightMode").text == "relativeToStartPoint"
    assert waylines.find(".//" + W + "executeHeightMode").text == "relativeToStartPoint"


def test_matrice_4t_and_camera_enums():
    template, waylines = files(draft())
    for root in (template, waylines):
        assert root.find(".//" + W + "droneEnumValue").text == "99"
        assert root.find(".//" + W + "droneSubEnumValue").text == "1"
        assert root.find(".//" + W + "payloadEnumValue").text == "89"
        assert root.find(".//" + W + "payloadPositionIndex").text == "0"


def test_matrice_4e_profile():
    template, waylines = files(draft(drone_model="matrice4e"))
    for root in (template, waylines):
        assert root.find(".//" + W + "droneEnumValue").text == "99"
        assert root.find(".//" + W + "droneSubEnumValue").text == "0"
        assert root.find(".//" + W + "payloadEnumValue").text == "88"


def test_waypoints_have_correct_lon_lat_order_and_continuous_ids():
    template, waylines = files(draft())
    for root in (template, waylines):
        points = root.findall(".//" + K + "Placemark")
        assert [p.find(W + "index").text for p in points] == ["0", "1"]
        assert points[0].find(".//" + K + "coordinates").text == "8.5,49.1"
        assert points[1].find(".//" + K + "coordinates").text == "8.6,49.2"
    assert all(p.find(W + "executeHeight").text == "50" for p in
               waylines.findall(".//" + K + "Placemark"))
    assert all(p.find(W + "useGlobalHeight").text == "1" for p in
               template.findall(".//" + K + "Placemark"))


def test_photo_action_is_only_on_requested_point():
    template, waylines = files(draft())
    for root in (template, waylines):
        points = root.findall(".//" + K + "Placemark")
        action = points[0].find(".//" + W + "actionActuatorFunc")
        assert action is not None and action.text == "takePhoto"
        assert points[1].find(".//" + W + "actionGroup") is None


def test_conservative_rc_loss_settings():
    _, waylines = files(draft())
    assert waylines.find(".//" + W + "exitOnRCLost").text == "executeLostAction"
    assert waylines.find(".//" + W + "executeRCLostAction").text == "goBack"
    assert waylines.find(".//" + W + "finishAction").text == "goHome"


@pytest.mark.parametrize("settings", [
    {"drone_model": "dock3"},
    {"speed_mps": 16.0},
    {"altitude_m": -1.0},
    {"finish_action": "autoLand"},
    {"name": "  "},
    {"unexpected_dji_command": True},
    {"waypoints": [{"latitude": 91.0, "longitude": 8.5}]},
    {"waypoints": [{"latitude": float("nan"), "longitude": 8.5}]},
])
def test_invalid_and_unsupported_missions_are_rejected(settings):
    with pytest.raises(ValidationError):
        draft(**settings)


def test_export_requires_two_waypoints():
    with pytest.raises(ValueError, match="between 2 and 500"):
        export_kmz(draft(waypoints=[{"latitude": 49.1, "longitude": 8.5}]),
                   timestamp_ms=1)


def test_rejects_negative_timestamp():
    with pytest.raises(ValueError):
        export_kmz(draft(), timestamp_ms=-1)
