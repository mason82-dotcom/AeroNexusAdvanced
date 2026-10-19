"""Strict, offline DJI heading-path migration regression tests.

No DJI connection, no Pilot 2 execution, no cloud operations, no flight approval.
The historical fixtures are generated from the exact prior AeroNexus XML writer
using its explicit legacy_heading_path switch, not guessed DJI KMZ semantics.
"""
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
import xml.etree.ElementTree as ET

import pytest

from aeronexus.wpml_export import (
    KML_NS, WPML_NS, WaypointMission, _xml, export_kmz, import_kmz,
)
from aeronexus.wpml_conformance import audit_kmz

K = "{" + KML_NS + "}"
W = "{" + WPML_NS + "}"
MODELS = ("matrice4t", "matrice4e", "mavic3e", "mavic3t", "mavic3m", "mavic3ta")


def mission(model="matrice4t", *, smooth=False, photos=False):
    points = [
        {"latitude": 49.1, "longitude": 8.5, "take_photo": photos},
        {"latitude": 49.2, "longitude": 8.6},
    ]
    if smooth:
        for point, angle in zip(points, (-30.0, 45.0)):
            point["heading_angle_deg"] = angle
    return WaypointMission.model_validate({
        "name": "offline-heading-compatibility",
        "drone_model": model,
        "waypoints": points,
        **({"heading_mode": "smoothTransition",
            "heading_path_mode": "counterClockwise"} if smooth else {}),
    })


def make_kmz(m, *, legacy_heading=False, legacy_camera=False):
    stream = BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as zipfile:
        for is_template, name in (
            (True, "wpmz/template.kml"),
            (False, "wpmz/waylines.wpml"),
        ):
            zipfile.writestr(
                name, _xml(
                    m, template=is_template, timestamp_ms=1760641200000,
                    legacy_heading_path=legacy_heading,
                    legacy_camera_params=legacy_camera,
                ),
            )
    return stream.getvalue()


def documents(blob):
    with ZipFile(BytesIO(blob)) as src:
        return [
            ET.fromstring(src.read(name))
            for name in ("wpmz/template.kml", "wpmz/waylines.wpml")
        ]


@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("smooth", [False, True])
def test_current_export_has_complete_heading_path_in_all_blocks(model, smooth):
    m = mission(model, smooth=smooth)
    blob = export_kmz(m, timestamp_ms=1760641200000)
    template, route = documents(blob)
    glob = template.find(".//" + W + "globalWaypointHeadingParam")
    assert glob is not None
    assert glob.findtext(W + "waypointHeadingPathMode") == "followBadArc"
    assert template.findtext(".//" + W + "templateType") == "waypoint"
    for point in route.findall(".//" + K + "Placemark"):
        heading = point.find(W + "waypointHeadingParam")
        assert heading is not None
        assert heading.findtext(W + "waypointHeadingPathMode") == (
            "counterClockwise" if smooth else "followBadArc"
        )
    assert import_kmz(blob).model_dump() == m.model_dump()
    findings = {x["code"] for x in audit_kmz(blob)["findings"]}
    assert "HEADING_PATH_MODE_INTEROP_UNVERIFIED" not in findings
    assert audit_kmz(blob)["full_dji_wpml_conformance_verified"] is False


@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("smooth", [False, True])
def test_previous_heading_format_is_imported_and_reexported_with_path(model, smooth):
    m = mission(model, smooth=smooth)
    old_blob = make_kmz(m, legacy_heading=True)
    legacy_audit = audit_kmz(old_blob)
    assert legacy_audit["editable_in_aeronexus"] is True
    assert "HEADING_PATH_MODE_INTEROP_UNVERIFIED" in {
        entry["code"] for entry in legacy_audit["findings"]
    }
    restored = import_kmz(old_blob)
    assert restored.model_dump() == m.model_dump()
    new_blob = export_kmz(restored, timestamp_ms=1760641200001)
    assert new_blob != old_blob
    assert import_kmz(new_blob).model_dump() == m.model_dump()
    assert "HEADING_PATH_MODE_INTEROP_UNVERIFIED" not in {
        entry["code"] for entry in audit_kmz(new_blob)["findings"]
    }


@pytest.mark.parametrize("model", ("matrice4t", "mavic3t", "mavic3m"))
def test_old_camera_and_old_heading_migrate_together(model):
    m = mission(model, photos=True)
    old_blob = make_kmz(m, legacy_heading=True, legacy_camera=True)
    assert import_kmz(old_blob).model_dump() == m.model_dump()
    assert audit_kmz(old_blob)["editable_in_aeronexus"] is True
    newer = export_kmz(import_kmz(old_blob), timestamp_ms=1760641200002)
    assert import_kmz(newer).model_dump() == m.model_dump()
    assert "HEADING_PATH_MODE_INTEROP_UNVERIFIED" not in {
        entry["code"] for entry in audit_kmz(newer)["findings"]
    }


@pytest.mark.parametrize("only_template", [True, False])
def test_inconsistent_heading_generations_are_never_combined(only_template):
    m = mission("matrice4t")
    current = documents(export_kmz(m, timestamp_ms=1))
    old = documents(make_kmz(m, legacy_heading=True))
    target = current if only_template else old
    source = old if only_template else current
    out = BytesIO()
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as zipfile:
        zipfile.writestr("wpmz/template.kml", ET.tostring(target[0]))
        zipfile.writestr("wpmz/waylines.wpml", ET.tostring(source[1]))
    with pytest.raises(ValueError, match="WPML settings disagree"):
        import_kmz(out.getvalue())
    assert audit_kmz(out.getvalue())["editable_in_aeronexus"] is False


def test_missing_only_one_waypoint_heading_path_is_rejected_not_repaired():
    m = mission()
    template, route = documents(export_kmz(m, timestamp_ms=1))
    one = route.findall(".//" + K + "Placemark")[0]
    heading = one.find(W + "waypointHeadingParam")
    heading.remove(heading.find(W + "waypointHeadingPathMode"))
    out = BytesIO()
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as zipfile:
        zipfile.writestr("wpmz/template.kml", ET.tostring(template))
        zipfile.writestr("wpmz/waylines.wpml", ET.tostring(route))
    with pytest.raises(ValueError, match="WPML settings disagree"):
        import_kmz(out.getvalue())
    assert audit_kmz(out.getvalue())["editable_in_aeronexus"] is False


def test_matrice4_stop_record_requires_no_guessed_lens_fields():
    m = WaypointMission.model_validate({
        "name": "stop recording",
        "drone_model": "matrice4t",
        "waypoints": [
            {"latitude": 49.1, "longitude": 8.5,
             "actions": [{"type": "startRecord"}]},
            {"latitude": 49.2, "longitude": 8.6,
             "actions": [{"type": "stopRecord"}]},
        ],
    })
    blob = export_kmz(m, timestamp_ms=1)
    for root in documents(blob):
        for action in root.findall(".//" + W + "action"):
            if action.findtext(W + "actionActuatorFunc") == "stopRecord":
                params = action.find(W + "actionActuatorFuncParam")
                assert params is not None
                assert params.findtext(W + "payloadPositionIndex") == "0"
                assert params.find(W + "payloadLensIndex") is None
                assert params.find(W + "useGlobalPayloadLensIndex") is None
    assert import_kmz(blob).model_dump() == m.model_dump()
