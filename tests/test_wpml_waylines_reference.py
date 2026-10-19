"""DJI waylines.wpml: offline executable-route contract regression tests.

Only the AeroNexus 1.0.2 waypoint subset, not generic DJI flight approval.
Reference: https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/waylines-wpml.html
"""
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
import xml.etree.ElementTree as ET

import pytest

from aeronexus.wpml_export import KML_NS, WPML_NS, WaypointMission, export_kmz, import_kmz
from aeronexus.wpml_conformance import audit_kmz
from aeronexus.wpml_required_fields import required_waypoint_findings

K, W = "{" + KML_NS + "}", "{" + WPML_NS + "}"
MODELS = ("matrice4e", "matrice4t", "mavic3e", "mavic3t", "mavic3m", "mavic3ta")
MISSION_FIELDS = ("flyToWaylineMode", "finishAction", "exitOnRCLost",
                  "takeOffSecurityHeight", "globalTransitionalSpeed",
                  "globalRTHHeight")
FOLDER_FIELDS = ("templateId", "waylineId", "autoFlightSpeed", "executeHeightMode")


def mission(model, *, smooth=False, curve=False):
    points = [
        {"latitude": 49.10, "longitude": 8.50},
        {"latitude": 49.11, "longitude": 8.51},
        {"latitude": 49.12, "longitude": 8.52},
    ]
    if smooth:
        for point, angle in zip(points, (-90.0, 0.0, 90.0)):
            point["heading_angle_deg"] = angle
    return WaypointMission.model_validate({
        "name": "OFFLINE_WAYLINES_TEST",
        "drone_model": model,
        "waypoints": points,
        "turn_mode": ("toPointAndStopWithContinuityCurvature"
                      if curve else "toPointAndStopWithDiscontinuityCurvature"),
        **({"heading_mode": "smoothTransition",
            "heading_path_mode": "clockwise"} if smooth else {}),
    })


def roots(m):
    kmz = export_kmz(m, timestamp_ms=42)
    with ZipFile(BytesIO(kmz)) as z:
        return ET.fromstring(z.read("wpmz/template.kml")), ET.fromstring(
            z.read("wpmz/waylines.wpml")), kmz


def repack(template, route):
    stream = BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as z:
        z.writestr("wpmz/template.kml", ET.tostring(template, encoding="utf-8"))
        z.writestr("wpmz/waylines.wpml", ET.tostring(route, encoding="utf-8"))
    return stream.getvalue()


@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("smooth,curve", [
    (False, False), (False, True), (True, False), (True, True),
])
def test_executable_wayline_contains_all_mode_specific_fields(model, smooth, curve):
    m = mission(model, smooth=smooth, curve=curve)
    template, route, blob = roots(m)
    assert required_waypoint_findings(template, route) == []
    assert import_kmz(blob).model_dump() == m.model_dump()
    assert audit_kmz(blob)["editable_in_aeronexus"] is True
    config = route.find(K + "Document/" + W + "missionConfig")
    for field in MISSION_FIELDS:
        assert config.findtext(W + field)
    assert config.findtext(W + "executeRCLostAction") == "goBack"
    template_folder = template.find(K + "Document/" + K + "Folder")
    folder = route.find(K + "Document/" + K + "Folder")
    for field in FOLDER_FIELDS:
        assert folder.findtext(W + field)
    assert folder.findtext(W + "templateId") == template_folder.findtext(W + "templateId")
    assert folder.findtext(W + "waylineId") == "0"
    assert folder.findtext(W + "executeHeightMode") == "relativeToStartPoint"
    assert folder.findtext(W + "autoFlightSpeed") == template_folder.findtext(W + "autoFlightSpeed")
    for block in ("droneInfo", "payloadInfo"):
        lhs = template.find(K + "Document/" + W + "missionConfig/" + W + block)
        rhs = route.find(K + "Document/" + W + "missionConfig/" + W + block)
        assert lhs is not None and rhs is not None
        assert ET.tostring(lhs) == ET.tostring(rhs)
    tpoints = template_folder.findall(K + "Placemark")
    rpoints = folder.findall(K + "Placemark")
    assert len(tpoints) == len(rpoints) == 3
    for index, (plan, execution) in enumerate(zip(tpoints, rpoints)):
        assert plan.findtext(W + "index") == execution.findtext(W + "index") == str(index)
        assert (
            plan.findtext(K + "Point/" + K + "coordinates")
            == execution.findtext(K + "Point/" + K + "coordinates")
        )
        for field in ("executeHeight", "waypointSpeed"):
            assert execution.findtext(W + field)
        heading = execution.find(W + "waypointHeadingParam")
        turn = execution.find(W + "waypointTurnParam")
        assert heading is not None and turn is not None
        assert heading.findtext(W + "waypointHeadingMode") == (
            "smoothTransition" if smooth else "followWayline"
        )
        assert heading.findtext(W + "waypointHeadingPathMode") == (
            "clockwise" if smooth else "followBadArc"
        )
        if smooth:
            assert heading.findtext(W + "waypointHeadingAngle")
        if curve:
            assert execution.findtext(W + "useStraightLine") == "1"
        assert turn.findtext(W + "waypointTurnMode") == (
            "toPointAndStopWithContinuityCurvature" if curve
            else "toPointAndStopWithDiscontinuityCurvature"
        )


@pytest.mark.parametrize("field,parent", [
    ("globalRTHHeight", "missionConfig"),
    ("templateId", "Folder"),
    ("waylineId", "Folder"),
    ("executeHeightMode", "Folder"),
    ("executeHeight", "Placemark"),
])
def test_missing_required_waylines_element_is_named_and_fails_closed(field, parent):
    template, route, _ = roots(mission("matrice4t"))
    root = route.find(K + "Document")
    if parent == "missionConfig":
        node = root.find(W + "missionConfig")
    elif parent == "Folder":
        node = root.find(K + "Folder")
    else:
        node = root.find(K + "Folder/" + K + "Placemark")
    node.remove(node.find(W + field))
    issues = required_waypoint_findings(template, route)
    assert any(
        finding["document"] == "waylines.wpml" and finding["field"] == "wpml:" + field
        for finding in issues
    )
    assert audit_kmz(repack(template, route))["editable_in_aeronexus"] is False


def test_extra_executable_folder_is_outside_own_single_waypoint_subset():
    template, route, _ = roots(mission("matrice4t"))
    doc = route.find(K + "Document")
    first = doc.find(K + "Folder")
    doc.append(ET.fromstring(ET.tostring(first)))
    result = audit_kmz(repack(template, route))
    assert result["editable_in_aeronexus"] is False
    assert result["full_dji_wpml_conformance_verified"] is False


def test_resource_member_is_not_silently_discarded_from_foreign_dji_kmz():
    template, route, _ = roots(mission("matrice4t"))
    stream = BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as z:
        z.writestr("wpmz/template.kml", ET.tostring(template))
        z.writestr("wpmz/waylines.wpml", ET.tostring(route))
        z.writestr("wpmz/res/sample.jpg", b"offline-synthetic-attachment")
    report = audit_kmz(stream.getvalue())
    assert report["editable_in_aeronexus"] is False
    assert any(
        entry["code"] == "OUTSIDE_TWO_DOCUMENT_SUBSET"
        for entry in report["findings"]
    )
