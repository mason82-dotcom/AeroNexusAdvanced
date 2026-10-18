"""Offline DJI WPML action exporter: matrix gating and lossless round trips."""
from io import BytesIO
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import pytest
from pydantic import ValidationError

from aeronexus.wpml_export import (
    WaypointMission, ACTION_MODEL_MATRIX, MODELS, WPML_NS,
    export_kmz, import_kmz,
)


def mission(model="mavic3e", actions=None):
    return WaypointMission.model_validate({
        "name": "Offline camera/gimbal plan",
        "drone_model": model,
        "waypoints": [
            {"latitude": 49.1, "longitude": 8.5, "take_photo": True,
             "actions": actions if actions is not None else [
                 {"type": "startRecord"},
                 {"type": "focus", "focus_x": 0.5, "focus_y": 0.25},
                 {"type": "zoom", "focal_length_mm": 35.0},
                 {"type": "gimbalRotate", "pitch_deg": -45.0},
                 {"type": "gimbalEvenlyRotate", "pitch_deg": -70.0},
             ]},
            {"latitude": 49.2, "longitude": 8.6,
             "actions": [{"type": "stopRecord"}]},
        ],
    })


@pytest.mark.parametrize("model", [
    "matrice4e", "matrice4t", "mavic3e", "mavic3t", "mavic3m",
])
def test_offline_camera_gimbal_roundtrip_for_explicit_wpml_matrix_models(model):
    plan = mission(model)
    data = export_kmz(plan, timestamp_ms=1760641200000)
    restored = import_kmz(data)
    assert restored.model_dump() == plan.model_dump()
    with ZipFile(BytesIO(data)) as z:
        for path in ("wpmz/template.kml", "wpmz/waylines.wpml"):
            root = ET.fromstring(z.read(path))
            ns = "{" + WPML_NS + "}"
            names = [e.text for e in root.findall(".//" + ns + "actionActuatorFunc")]
            assert names == [
                "takePhoto", "startRecord", "focus", "zoom",
                "gimbalRotate", "gimbalEvenlyRotate", "stopRecord",
            ]
            groups = root.findall(".//" + ns + "actionGroup")
            assert len(groups) == 7
            assert len({x.find(ns + "actionGroupId").text for x in groups}) == 7
            between = [g for g in groups
                       if g.find(".//" + ns + "actionActuatorFunc").text
                       == "gimbalEvenlyRotate"]
            assert len(between) == 1
            assert between[0].find(ns + "actionGroupStartIndex").text == "0"
            assert between[0].find(ns + "actionGroupEndIndex").text == "1"
            assert between[0].find(ns + "actionTrigger/" + ns + "actionTriggerType").text == "betweenAdjacentPoints"


def test_m3ta_is_identified_but_does_not_inherit_unsupported_action_table():
    assert "mavic3ta" in MODELS
    assert ACTION_MODEL_MATRIX["mavic3ta"] == frozenset()
    with pytest.raises(ValidationError, match="not evidenced"):
        mission("mavic3ta")
    # Legacy photo-only missions remain representable for all six profiles.
    basic = WaypointMission.model_validate({
        "name": "M3TA offline photo plan", "drone_model": "mavic3ta",
        "waypoints": [{"latitude": 49.1, "longitude": 8.5, "take_photo": True},
                      {"latitude": 49.2, "longitude": 8.6}],
    })
    assert import_kmz(export_kmz(basic, timestamp_ms=1)).model_dump() == basic.model_dump()


def test_legacy_point_json_shape_is_unchanged_when_no_additional_actions():
    plain = WaypointMission.model_validate({
        "name": "Legacy", "waypoints": [
            {"latitude": 49.1, "longitude": 8.5, "take_photo": True},
            {"latitude": 49.2, "longitude": 8.6, "take_photo": False},
        ],
    })
    assert plain.model_dump()["waypoints"] == [
        {"latitude": 49.1, "longitude": 8.5, "take_photo": True},
        {"latitude": 49.2, "longitude": 8.6, "take_photo": False},
    ]


@pytest.mark.parametrize("action", [
    {"type": "unexpectedVendorAction"},
    {"type": "focus", "focus_x": 1.5, "focus_y": 0.5},
    {"type": "zoom", "focal_length_mm": 0.0},
    {"type": "zoom", "focal_length_mm": float("nan")},
    {"type": "gimbalRotate", "pitch_deg": 25.0},
    {"type": "gimbalEvenlyRotate", "pitch_deg": float("inf")},
    {"type": "focus", "focus_x": 0.3, "focus_y": 0.4, "private_parameter": 1},
])
def test_unrecognized_or_out_of_bounds_params_are_rejected(action):
    with pytest.raises(ValidationError):
        mission(actions=[action])


def test_even_gimbal_rotation_cannot_execute_at_final_point():
    with pytest.raises(ValidationError, match="following waypoint"):
        WaypointMission.model_validate({
            "name": "No next segment", "drone_model": "matrice4t",
            "waypoints": [
                {"latitude": 49.1, "longitude": 8.5},
                {"latitude": 49.2, "longitude": 8.6,
                 "actions": [{"type": "gimbalEvenlyRotate", "pitch_deg": -30.0}]},
            ],
        })


def test_closed_return_waypoint_does_not_repeat_camera_commands():
    m = WaypointMission.model_validate({
        "name": "Closed action route", "close_route": True,
        "drone_model": "mavic3e", "waypoints": [
            {"latitude": 49.1, "longitude": 8.5,
             "actions": [{"type": "startRecord"}]},
            {"latitude": 49.2, "longitude": 8.6},
            {"latitude": 49.2, "longitude": 8.7,
             "actions": [{"type": "gimbalEvenlyRotate", "pitch_deg": -20.0}]},
        ],
    })
    back = import_kmz(export_kmz(m, timestamp_ms=1))
    assert back.close_route is True
    assert back.model_dump() == m.model_dump()


def test_action_mutation_in_executable_xml_fails_closed():
    data = export_kmz(mission(), timestamp_ms=1)
    changed = BytesIO()
    with ZipFile(BytesIO(data)) as src, ZipFile(changed, "w") as dst:
        for entry in src.namelist():
            body = src.read(entry)
            if entry == "wpmz/waylines.wpml":
                body = body.replace(b"gimbalPitchRotateAngle>-45<",
                                    b"gimbalPitchRotateAngle>23<", 1)
            dst.writestr(entry, body)
    with pytest.raises(ValueError):
        import_kmz(changed.getvalue())
