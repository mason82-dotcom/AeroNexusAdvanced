"""DJI WPML mandatory-field contract for the implemented waypoint-only subset.

Reference: official DJI Cloud API documentation, 19 Oct 2026:
template.kml, waylines.wpml and Common Elements.

Rules apply to the *selected template type and actuator*. Fields of other
template families, other actuators, and container-optional elements are NOT
required for ordinary AeroNexus waypoint exports.

This is static XML contract coverage, not DJI Pilot 2 or flight certification.
"""
from io import BytesIO
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import pytest

from aeronexus.wpml_export import (
    KML_NS, WPML_NS, WaypointMission, export_kmz,
)
from aeronexus.wpml_conformance import audit_kmz

K = "{" + KML_NS + "}"
W = "{" + WPML_NS + "}"
AIRCRAFT = ("matrice4e", "matrice4t", "mavic3e", "mavic3t", "mavic3m", "mavic3ta")


def mission(model="matrice4t", *, curve=False, smooth=False, camera=False):
    pts = [
        {"latitude": 49.10, "longitude": 8.50},
        {"latitude": 49.11, "longitude": 8.51},
        {"latitude": 49.12, "longitude": 8.52},
    ]
    if smooth:
        for p, angle in zip(pts, (-70., 0., 120.)):
            p["heading_angle_deg"] = angle
    if camera:
        pts[0]["take_photo"] = True
        pts[0]["actions"] = [
            {"type": "startRecord"},
            {"type": "focus", "focus_x": 0.5, "focus_y": 0.3},
            {"type": "zoom", "focal_length_mm": 40.0},
            {"type": "gimbalRotate", "pitch_deg": -45.0},
            {"type": "gimbalEvenlyRotate", "pitch_deg": -60.0},
        ]
        pts[1]["actions"] = [{"type": "stopRecord"}]
    kwargs = {
        "name": "Synthetic, offline",
        "drone_model": model,
        "waypoints": pts,
        "turn_mode": ("toPointAndStopWithContinuityCurvature"
                      if curve else "toPointAndStopWithDiscontinuityCurvature"),
    }
    if smooth:
        kwargs.update(heading_mode="smoothTransition",
                      heading_path_mode="followBadArc")
    return WaypointMission.model_validate(kwargs)


def documents(m):
    data = export_kmz(m, timestamp_ms=42)
    with ZipFile(BytesIO(data)) as z:
        assert sorted(z.namelist()) == ["wpmz/template.kml", "wpmz/waylines.wpml"]
        return (
            ET.fromstring(z.read("wpmz/template.kml")),
            ET.fromstring(z.read("wpmz/waylines.wpml")),
            data,
        )


def required(node, *names):
    for name in names:
        child = node.find(W + name)
        assert child is not None, f"DJI required WPML child is missing: {name}"
        assert child.text and child.text.strip(), f"Empty DJI required WPML field: {name}"


@pytest.mark.parametrize("model", AIRCRAFT)
@pytest.mark.parametrize("curve,smooth", [
    (False, False), (True, False), (False, True), (True, True),
])
def test_global_required_fields_in_both_documents(model, curve, smooth):
    template, waylines, blob = documents(
        mission(model, curve=curve, smooth=smooth)
    )
    assert audit_kmz(blob)["editable_in_aeronexus"]
    for root in (template, waylines):
        assert root.tag == K + "kml"
        doc = root.find(K + "Document")
        assert doc is not None
        config = doc.find(W + "missionConfig")
        assert config is not None
        required(config, "flyToWaylineMode", "finishAction", "exitOnRCLost",
                 "takeOffSecurityHeight", "globalTransitionalSpeed")
        # Required iff exitOnRCLost=executeLostAction
        if config.findtext(W + "exitOnRCLost") == "executeLostAction":
            required(config, "executeRCLostAction")
        required(config.find(W + "droneInfo"), "droneEnumValue",
                 "droneSubEnumValue")
        required(config.find(W + "payloadInfo"), "payloadEnumValue",
                 "payloadPositionIndex")
        # These are conditional on parent presence, not globally required:
        param = doc.find(".//" + W + "payloadParam")
        if param is not None:
            required(param, "payloadPositionIndex", "imageFormat")
        reroute = config.find(W + "autoRerouteInfo")
        if reroute is not None:
            required(reroute, "missionAutoRerouteMode",
                     "transitionalAutoRerouteMode")

    tconfig = template.find(K + "Document/" + W + "missionConfig")
    rconfig = waylines.find(K + "Document/" + W + "missionConfig")
    required(rconfig, "globalRTHHeight")
    t = template.find(K + "Document/" + K + "Folder")
    r = waylines.find(K + "Document/" + K + "Folder")
    required(t, "templateType", "templateId", "autoFlightSpeed",
             "gimbalPitchMode", "globalWaypointTurnMode", "globalHeight")
    required(r, "templateId", "waylineId", "executeHeightMode",
             "autoFlightSpeed")
    coords = t.find(W + "waylineCoordinateSysParam")
    assert coords is not None
    required(coords, "coordinateMode", "heightMode")
    assert coords.findtext(W + "coordinateMode") == "WGS84"
    assert coords.findtext(W + "heightMode") == "relativeToStartPoint"
    assert t.findtext(W + "templateType") == "waypoint"
    if curve:
        # Conditional mandatory according to DJI template.kml table.
        required(t, "globalUseStraightLine")
    assert t.find(W + "globalWaypointHeadingParam") is not None
    required(t.find(W + "globalWaypointHeadingParam"), "waypointHeadingMode")

    tpoints = t.findall(K + "Placemark")
    rpoints = r.findall(K + "Placemark")
    assert len(tpoints) == len(rpoints) == 3
    for index, (plan, flight) in enumerate(zip(tpoints, rpoints)):
        for point in (plan, flight):
            pt = point.find(K + "Point")
            assert pt is not None and pt.find(K + "coordinates") is not None
            assert "," in pt.findtext(K + "coordinates")
            required(point, "index")
            assert point.findtext(W + "index") == str(index)
        required(plan, "useGlobalHeight", "useGlobalSpeed",
                 "useGlobalHeadingParam", "useGlobalTurnParam")
        if t.findtext(W + "gimbalPitchMode") == "usePointSetting":
            required(plan, "gimbalPitchAngle")
        assert plan.findtext(W + "useGlobalHeight") == "1"
        assert plan.findtext(W + "useGlobalSpeed") == "1"
        if plan.findtext(W + "useGlobalHeadingParam") == "0":
            heading = plan.find(W + "waypointHeadingParam")
            assert heading is not None
            required(heading, "waypointHeadingMode")
            if heading.findtext(W + "waypointHeadingMode") == "smoothTransition":
                required(heading, "waypointHeadingAngle",
                         "waypointHeadingPathMode")
        if plan.findtext(W + "useGlobalTurnParam") == "0":
            required(plan.find(W + "waypointTurnParam"), "waypointTurnMode")
        required(flight, "executeHeight", "waypointSpeed")
        heading = flight.find(W + "waypointHeadingParam")
        required(heading, "waypointHeadingMode")
        if smooth:
            required(heading, "waypointHeadingAngle", "waypointHeadingPathMode")
        turn = flight.find(W + "waypointTurnParam")
        required(turn, "waypointTurnMode")
        if curve:
            # Mandatory iff selected continuous curvature stop mode.
            required(flight, "useStraightLine")
            assert flight.findtext(W + "useStraightLine") == "1"
        # DampingDist > 0 is mandatory for coordinated/pass-through modes,
        # which are deliberately not supported by our exported mission model.


def test_known_heading_path_discrepancy_is_identified_not_certified():
    template, route, blob = documents(mission())
    assert template.find(
        ".//" + W + "globalWaypointHeadingParam/" + W + "waypointHeadingPathMode"
    ) is None
    assert route.find(
        ".//" + W + "waypointHeadingParam/" + W + "waypointHeadingPathMode"
    ) is None
    report = audit_kmz(blob)
    assert report["full_dji_wpml_conformance_verified"] is False
    assert "HEADING_PATH_MODE_INTEROP_UNVERIFIED" in {
        item["code"] for item in report["findings"]
    }


def test_optional_payload_param_is_not_mistaken_for_missing_payload_info():
    template, route, _ = documents(mission())
    for root in (template, route):
        assert root.find(".//" + W + "payloadInfo") is not None
        assert root.find(".//" + W + "payloadParam") is None


def test_legacy_global_straight_line_flag_is_documented_compatibility_gap():
    template, _, _ = documents(mission(curve=False))
    # Preserve the legacy canonical export; DJI describes this field as
    # required iff a curvature turn mode is selected.
    assert template.findtext(".//" + W + "globalUseStraightLine") == "1"


@pytest.mark.parametrize("model", ["matrice4t", "matrice4e", "mavic3e", "mavic3t", "mavic3m"])
def test_mandatory_fields_for_seven_supported_action_types(model):
    template, route, blob = documents(mission(model, camera=True))
    assert audit_kmz(blob)["editable_in_aeronexus"]
    expected = {"takePhoto", "startRecord", "stopRecord", "focus", "zoom",
                "gimbalRotate", "gimbalEvenlyRotate"}
    for root in (template, route):
        seen = set()
        for point in root.findall(".//" + K + "Placemark"):
            for group in point.findall(W + "actionGroup"):
                required(group, "actionGroupId", "actionGroupStartIndex",
                         "actionGroupEndIndex", "actionGroupMode")
                trigger = group.find(W + "actionTrigger")
                required(trigger, "actionTriggerType")
                item = group.find(W + "action")
                required(item, "actionId", "actionActuatorFunc")
                kind = item.findtext(W + "actionActuatorFunc")
                seen.add(kind)
                params = item.find(W + "actionActuatorFuncParam")
                assert params is not None
                required(params, "payloadPositionIndex")
                if kind in ("takePhoto", "startRecord"):
                    required(params, "fileSuffix", "useGlobalPayloadLensIndex")
                    if model in {"matrice4t", "matrice4e"}:
                        required(params, "payloadLensIndex")
                elif kind == "focus":
                    required(params, "isPointFocus", "focusX", "focusY",
                             "isInfiniteFocus")
                elif kind == "zoom":
                    required(params, "focalLength")
                elif kind == "gimbalRotate":
                    required(params, "gimbalHeadingYawBase", "gimbalRotateMode",
                             "gimbalPitchRotateEnable", "gimbalPitchRotateAngle",
                             "gimbalRollRotateEnable", "gimbalRollRotateAngle",
                             "gimbalYawRotateEnable", "gimbalYawRotateAngle",
                             "gimbalRotateTimeEnable", "gimbalRotateTime")
                elif kind == "gimbalEvenlyRotate":
                    required(params, "gimbalPitchRotateAngle")
                    assert trigger.findtext(W + "actionTriggerType") == "betweenAdjacentPoints"
        assert seen == expected


@pytest.mark.parametrize("code,subset", [
    ("toPointAndPassWithContinuityCurvature", "unsupported"),
    ("coordinateTurn", "unsupported"),
])
def test_disallowed_turn_styles_never_enter_mandatory_field_matrix(code, subset):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        mission(curve=False).model_copy(update={"turn_mode": code}).__class__.model_validate(
            {**mission().model_dump(), "turn_mode": code}
        )
