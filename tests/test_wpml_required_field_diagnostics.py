"""Standalone mandatory-field diagnostics: missing/conditional vs optional.

The tests use synthetic in-memory KMZ fixtures only. No drone or cloud.
"""
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
import xml.etree.ElementTree as ET

import pytest

from aeronexus.wpml_required_fields import required_waypoint_findings
from aeronexus.wpml_conformance import audit_kmz
from aeronexus.wpml_export import KML_NS, WPML_NS, WaypointMission, export_kmz

K, W = "{" + KML_NS + "}", "{" + WPML_NS + "}"


def sample(curve=False, smooth=False, action=False):
    points = [
        {"latitude": 49.10, "longitude": 8.51, "take_photo": action},
        {"latitude": 49.11, "longitude": 8.52},
    ]
    if action:
        points[0]["actions"] = [{"type": "startRecord"},
                                 {"type": "gimbalRotate", "pitch_deg": -45.0}]
        points[1]["actions"] = [{"type": "stopRecord"}]
    if smooth:
        points[0]["heading_angle_deg"] = -90.
        points[1]["heading_angle_deg"] = 90.
    return WaypointMission.model_validate({
        "name": "PRIVATE_MISSION_NEVER_LOG",
        "waypoints": points,
        "turn_mode": ("toPointAndStopWithContinuityCurvature" if curve
                      else "toPointAndStopWithDiscontinuityCurvature"),
        **({"heading_mode": "smoothTransition",
            "heading_path_mode": "followBadArc"} if smooth else {}),
    })


def roots(m):
    data = export_kmz(m, timestamp_ms=1)
    with ZipFile(BytesIO(data)) as source:
        return (
            ET.fromstring(source.read("wpmz/template.kml")),
            ET.fromstring(source.read("wpmz/waylines.wpml")),
        )


def rebuilt(template, route):
    buf = BytesIO()
    with ZipFile(buf, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("wpmz/template.kml", ET.tostring(template, encoding="utf-8"))
        archive.writestr("wpmz/waylines.wpml", ET.tostring(route, encoding="utf-8"))
    return buf.getvalue()


def expect_field(result, *, document, field, code):
    assert {"document": document, "field": field, "code": code, "severity": "error"} in result


@pytest.mark.parametrize("curve,smooth,action", [
    (False, False, False), (False, False, True),
    (True, False, False), (True, False, True),
    (False, True, False), (False, True, True),
    (True, True, False), (True, True, True),
])
def test_canonical_fields_are_complete_under_supported_conditions(curve, smooth, action):
    template, route = roots(sample(curve, smooth, action))
    assert required_waypoint_findings(template, route) == []
    report = audit_kmz(rebuilt(template, route))
    assert report["editable_in_aeronexus"] is True


def test_required_field_is_precisely_identified_without_private_data():
    t, r = roots(sample())
    config = t.find(K + "Document/" + W + "missionConfig")
    config.remove(config.find(W + "globalTransitionalSpeed"))
    results = required_waypoint_findings(t, r)
    expect_field(results, document="template.kml",
                 field="wpml:globalTransitionalSpeed",
                 code="DJI_REQUIRED_FIELD_MISSING")
    report = audit_kmz(rebuilt(t, r))
    assert report["editable_in_aeronexus"] is False
    expect_field(report["findings"], document="template.kml",
                 field="wpml:globalTransitionalSpeed",
                 code="DJI_REQUIRED_FIELD_MISSING")
    assert "PRIVATE_MISSION_NEVER_LOG" not in str(report)
    assert "49.10" not in str(report)


def test_execute_lost_action_mandatory_only_with_its_guard():
    t, r = roots(sample())
    config = r.find(K + "Document/" + W + "missionConfig")
    config.remove(config.find(W + "executeRCLostAction"))
    results = required_waypoint_findings(t, r)
    expect_field(results, document="waylines.wpml",
                 field="wpml:executeRCLostAction",
                 code="DJI_CONDITIONAL_FIELD_MISSING")


def test_continuous_curve_requires_straight_line_flag():
    t, r = roots(sample(curve=True))
    first = r.find(".//" + K + "Placemark")
    first.remove(first.find(W + "useStraightLine"))
    results = required_waypoint_findings(t, r)
    expect_field(results, document="waylines.wpml",
                 field="wpml:useStraightLine",
                 code="DJI_CONDITIONAL_FIELD_MISSING")


def test_continuous_curve_requires_global_straight_line_flag():
    t, r = roots(sample(curve=True))
    folder = t.find(K + "Document/" + K + "Folder")
    folder.remove(folder.find(W + "globalUseStraightLine"))
    results = required_waypoint_findings(t, r)
    expect_field(results, document="template.kml",
                 field="wpml:globalUseStraightLine",
                 code="DJI_CONDITIONAL_FIELD_MISSING")


def test_gimbal_action_missing_angle_is_precisely_reported():
    t, r = roots(sample(action=True))
    for action in r.findall(".//" + W + "action"):
        if action.findtext(W + "actionActuatorFunc") == "gimbalRotate":
            params = action.find(W + "actionActuatorFuncParam")
            params.remove(params.find(W + "gimbalPitchRotateAngle"))
    results = required_waypoint_findings(t, r)
    expect_field(results, document="waylines.wpml",
                 field="wpml:gimbalPitchRotateAngle",
                 code="DJI_CONDITIONAL_FIELD_MISSING")


def test_optional_payload_parameter_block_is_not_globally_mandatory():
    t, r = roots(sample())
    assert required_waypoint_findings(t, r) == []
    folder = t.find(K + "Document/" + K + "Folder")
    param = ET.SubElement(folder, W + "payloadParam")
    ET.SubElement(param, W + "payloadPositionIndex").text = "0"
    results = required_waypoint_findings(t, r)
    expect_field(results, document="template.kml",
                 field="wpml:imageFormat",
                 code="DJI_CONDITIONAL_FIELD_MISSING")


def test_non_waypoint_template_families_are_not_misclassified():
    t, r = roots(sample())
    t.find(".//" + W + "templateType").text = "mapping3d"
    assert required_waypoint_findings(t, r) == []


def test_heading_path_dji_interoperability_remains_an_advisory():
    t, r = roots(sample())
    assert required_waypoint_findings(t, r) == []
    report = audit_kmz(rebuilt(t, r))
    assert "HEADING_PATH_MODE_INTEROP_UNVERIFIED" in {
        item["code"] for item in report["findings"]
    }
    assert report["full_dji_wpml_conformance_verified"] is False
