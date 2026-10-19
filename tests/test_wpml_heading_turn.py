"""Opt-in WPML yaw and curvature-stop mode regression tests.

No DJI connection, flight authorization or production workspace writes.
"""
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
import xml.etree.ElementTree as ET

import pytest
from pydantic import ValidationError

from aeronexus.wpml_conformance import audit_kmz
from aeronexus.wpml_export import (
    KML_NS, WPML_NS, WaypointMission, export_kmz, import_kmz,
)

K = "{" + KML_NS + "}"
W = "{" + WPML_NS + "}"


def mission(**overrides):
    data = {
        "name": "WPML Offline QA",
        "drone_model": "matrice4t",
        "waypoints": [
            {"latitude": 49.1, "longitude": 8.51, "take_photo": True},
            {"latitude": 49.11, "longitude": 8.52, "take_photo": False},
            {"latitude": 49.12, "longitude": 8.53, "take_photo": False},
        ],
    }
    data.update(overrides)
    return WaypointMission.model_validate(data)


def smooth_points():
    return [
        {"latitude": 49.1, "longitude": 8.51, "heading_angle_deg": -45.0},
        {"latitude": 49.11, "longitude": 8.52, "heading_angle_deg": 0.0},
        {"latitude": 49.12, "longitude": 8.53, "heading_angle_deg": 90.0},
    ]


def roots(blob):
    with ZipFile(BytesIO(blob)) as archive:
        return [
            ET.fromstring(archive.read(name))
            for name in ("wpmz/template.kml", "wpmz/waylines.wpml")
        ]


def assert_roundtrip(m):
    exported = export_kmz(m, timestamp_ms=1792367700000)
    restored = import_kmz(exported)
    assert restored.model_dump() == m.model_dump()
    audit = audit_kmz(exported)
    assert audit["editable_in_aeronexus"] is True
    if m.heading_mode == "smoothTransition":
        assert "HEADING_PATH_MODE_INTEROP_UNVERIFIED" not in {
            item["code"] for item in audit["findings"]
        }
    return roots(exported)


def test_default_serialization_remains_backward_compatible():
    m = mission()
    d = m.model_dump()
    assert "heading_mode" not in d
    assert "heading_path_mode" not in d
    assert "turn_mode" not in d
    assert all("heading_angle_deg" not in point for point in d["waypoints"])
    for root in assert_roundtrip(m):
        assert root.find(".//" + W + "waypointHeadingAngle") is None
        assert root.find(".//" + W + "waypointHeadingPathMode") is None
        assert root.find(".//" + W + "waypointTurnMode") is None or all(
            e.text == "toPointAndStopWithDiscontinuityCurvature"
            for e in root.findall(".//" + W + "waypointTurnMode")
        )


@pytest.mark.parametrize("model", ["matrice4t", "matrice4e", "mavic3e", "mavic3t", "mavic3m", "mavic3ta"])
@pytest.mark.parametrize("path", ["clockwise", "counterClockwise", "followBadArc"])
def test_smooth_heading_at_every_waypoint_in_both_documents(model, path):
    m = mission(
        drone_model=model,
        heading_mode="smoothTransition",
        heading_path_mode=path,
        waypoints=smooth_points(),
    )
    template, route = assert_roundtrip(m)
    for root in (template, route):
        points = root.findall(".//" + K + "Placemark")
        for point, angle in zip(points, (-45, 0, 90)):
            heading = point.find(W + "waypointHeadingParam")
            assert heading.findtext(W + "waypointHeadingMode") == "smoothTransition"
            assert heading.findtext(W + "waypointHeadingAngle") == str(angle)
            assert heading.findtext(W + "waypointHeadingPathMode") == path
            if root is template:
                assert point.findtext(W + "useGlobalHeadingParam") == "0"
    assert all(p.findtext(W + "waypointTurnParam/" + W + "waypointTurnMode") ==
               "toPointAndStopWithDiscontinuityCurvature"
               for p in route.findall(".//" + K + "Placemark"))


@pytest.mark.parametrize("mode", [
    "toPointAndStopWithDiscontinuityCurvature",
    "toPointAndStopWithContinuityCurvature",
])
def test_curvature_still_stops_at_every_waypoint(mode):
    m = mission(turn_mode=mode)
    template, route = assert_roundtrip(m)
    assert template.findtext(".//" + W + "globalWaypointTurnMode") == mode
    for point in route.findall(".//" + K + "Placemark"):
        assert point.findtext(W + "waypointTurnParam/" + W + "waypointTurnMode") == mode
        if mode == "toPointAndStopWithContinuityCurvature":
            assert point.findtext(W + "useStraightLine") == "1"
            assert point.find(W + "waypointTurnParam/" + W + "waypointTurnDampingDist") is None
        else:
            assert point.find(W + "useStraightLine") is None
            assert point.findtext(W + "waypointTurnParam/" + W + "waypointTurnDampingDist") == "0"


def test_smooth_heading_combines_with_curve_stop_offline():
    m = mission(
        heading_mode="smoothTransition",
        heading_path_mode="followBadArc",
        turn_mode="toPointAndStopWithContinuityCurvature",
        waypoints=smooth_points(),
    )
    assert_roundtrip(m)


@pytest.mark.parametrize("changes", [
    {"heading_mode": "smoothTransition", "heading_path_mode": "followBadArc"},
    {"heading_mode": "smoothTransition", "waypoints": smooth_points()},
    {"heading_mode": "smoothTransition", "heading_path_mode": "sideways", "waypoints": smooth_points()},
    {"heading_mode": "fixed"},
    {"heading_mode": "followWayline", "heading_path_mode": "clockwise"},
    {"heading_mode": "followWayline", "waypoints": smooth_points()},
    {"heading_mode": "smoothTransition", "heading_path_mode": "clockwise",
     "waypoints": smooth_points(), "close_route": True},
    {"heading_mode": "towardPOI"},
    {"turn_mode": "toPointAndPassWithContinuityCurvature"},
    {"turn_mode": "coordinateTurn"},
    {"turn_mode": "fastTurn"},
])
def test_unsupported_heading_or_turn_modes_fail_closed(changes):
    with pytest.raises(ValidationError):
        mission(**changes)


@pytest.mark.parametrize("angle", [float("nan"), float("inf"), float("-inf"), -180.01, 180.01])
def test_out_of_range_or_nonfinite_angle_is_rejected(angle):
    points = smooth_points()
    points[1]["heading_angle_deg"] = angle
    with pytest.raises(ValidationError):
        mission(heading_mode="smoothTransition", heading_path_mode="clockwise",
                waypoints=points)


def test_missing_one_angle_is_rejected():
    points = smooth_points()
    del points[1]["heading_angle_deg"]
    with pytest.raises(ValidationError):
        mission(heading_mode="smoothTransition", heading_path_mode="clockwise",
                waypoints=points)


def test_mixed_heading_mode_template_mutation_fails_closed():
    m = mission(heading_mode="smoothTransition",
                heading_path_mode="followBadArc", waypoints=smooth_points())
    original = export_kmz(m, timestamp_ms=1)
    dest = BytesIO()
    with ZipFile(BytesIO(original)) as inp, ZipFile(dest, "w", compression=ZIP_DEFLATED) as out:
        for name in inp.namelist():
            data = inp.read(name)
            if name == "wpmz/template.kml":
                root = ET.fromstring(data)
                first = root.find(".//" + K + "Placemark")
                first.find(W + "waypointHeadingParam/" + W + "waypointHeadingAngle").text = "40"
                data = ET.tostring(root)
            out.writestr(name, data)
    with pytest.raises(ValueError, match="WPML settings disagree"):
        import_kmz(dest.getvalue())
    assert audit_kmz(dest.getvalue())["editable_in_aeronexus"] is False


def test_mixed_per_waypoint_paths_cannot_be_silently_normalized():
    m = mission(heading_mode="smoothTransition",
                heading_path_mode="followBadArc", waypoints=smooth_points())
    original = export_kmz(m, timestamp_ms=1)
    dest = BytesIO()
    with ZipFile(BytesIO(original)) as inp, ZipFile(dest, "w", compression=ZIP_DEFLATED) as out:
        for name in inp.namelist():
            data = inp.read(name)
            if name == "wpmz/waylines.wpml":
                root = ET.fromstring(data)
                points = root.findall(".//" + K + "Placemark")
                points[1].find(W + "waypointHeadingParam/" + W + "waypointHeadingPathMode").text = "clockwise"
                data = ET.tostring(root)
            out.writestr(name, data)
    with pytest.raises(ValueError, match="Mixed or inconsistent"):
        import_kmz(dest.getvalue())


def test_legacy_closed_route_still_roundtrips():
    m = mission(close_route=True)
    assert_roundtrip(m)


def test_missing_conditional_straight_line_flag_cannot_pass_import():
    m = mission(turn_mode="toPointAndStopWithContinuityCurvature")
    original = export_kmz(m, timestamp_ms=1)
    dest = BytesIO()
    with ZipFile(BytesIO(original)) as inp, ZipFile(dest, "w", compression=ZIP_DEFLATED) as out:
        for name in inp.namelist():
            data = inp.read(name)
            if name == "wpmz/waylines.wpml":
                root = ET.fromstring(data)
                first = root.find(".//" + K + "Placemark")
                first.remove(first.find(W + "useStraightLine"))
                data = ET.tostring(root)
            out.writestr(name, data)
    with pytest.raises(ValueError, match="WPML settings disagree"):
        import_kmz(dest.getvalue())
    assert audit_kmz(dest.getvalue())["editable_in_aeronexus"] is False


def test_continuous_stop_never_writes_damping_without_selected_turn_mode():
    m = mission(turn_mode="toPointAndStopWithContinuityCurvature")
    for root in assert_roundtrip(m):
        if root.findtext(".//" + W + "executeHeightMode") is not None:
            assert root.findall(".//" + W + "useStraightLine")
            assert not root.findall(".//" + W + "waypointTurnDampingDist")
