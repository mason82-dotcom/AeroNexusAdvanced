"""Read-only WPML conformance audit regression tests (no drone/Cloud access)."""
from io import BytesIO
import json
from zipfile import ZipFile, ZIP_DEFLATED

import pytest

from aeronexus.wpml_conformance import audit_kmz, main
from aeronexus.wpml_export import WaypointMission, export_kmz, WPML_NS


def mission(model="matrice4t"):
    extra = (
        [{"type": "startRecord"}] if model != "mavic3ta" else []
    )
    finish = (
        [{"type": "stopRecord"}] if model != "mavic3ta" else []
    )
    return WaypointMission.model_validate({
        "name": "PRIVATE_NAME_MUST_NOT_LEAK",
        "drone_model": model,
        "waypoints": [
            {"latitude": 49.1, "longitude": 8.5, "take_photo": True, "actions": extra},
            {"latitude": 49.2, "longitude": 8.6, "actions": finish},
        ],
    })


def kmz(model="matrice4t"):
    return export_kmz(mission(model), timestamp_ms=1792367700000)


def replace_member(archive_bytes, member, transform):
    dest = BytesIO()
    with ZipFile(BytesIO(archive_bytes)) as original:
        with ZipFile(dest, "w", compression=ZIP_DEFLATED) as result:
            for name in original.namelist():
                payload = original.read(name)
                if name == member:
                    payload = transform(payload)
                result.writestr(name, payload)
    return dest.getvalue()


@pytest.mark.parametrize("model", [
    "matrice4e", "matrice4t", "mavic3e", "mavic3t", "mavic3m", "mavic3ta",
])
def test_own_mission_editable_without_claiming_dji_acceptance(model):
    result = audit_kmz(kmz(model))
    assert result["status"] == "supported_subset"
    assert result["editable_in_aeronexus"] is True
    assert result["wpml_schema"] == "1.0.2"
    assert result["waypoint_count"] == 2
    assert result["flight_compatibility_verified"] is False
    assert result["dji_pilot2_import_verified"] is False
    assert result["full_dji_wpml_conformance_verified"] is False
    assert not [x for x in result["findings"] if x["severity"] == "error"]
    assert "PRIVATE_NAME_MUST_NOT_LEAK" not in json.dumps(result)
    expected_actions = 2 if model == "mavic3ta" else 6
    # Count both template.kml and waylines.wpml occurrences, not flight events.
    assert result["action_count"] == expected_actions


@pytest.mark.parametrize("data,code", [
    (b"", "INVALID_SIZE"),
    (b"not a zip", "INVALID_ZIP_OR_XML"),
    (b"x" * (2 * 1024 * 1024 + 1), "INVALID_SIZE"),
])
def test_rejects_unsafe_or_invalid_container(data, code):
    result = audit_kmz(data)
    assert result["status"] == "invalid"
    assert result["editable_in_aeronexus"] is False
    assert code in {item["code"] for item in result["findings"]}


def test_10_6_is_not_assumed_semantically_compatible():
    data = kmz()
    for member in ("wpmz/template.kml", "wpmz/waylines.wpml"):
        data = replace_member(
            data, member, lambda body: body.replace(
                WPML_NS.encode(), b"http://www.dji.com/wpmz/1.0.6"
            ),
        )
    result = audit_kmz(data)
    assert result["status"] == "unsupported"
    assert result["wpml_schema"] == "1.0.6"
    assert result["editable_in_aeronexus"] is False
    assert result["findings"][0]["code"] == "WPML_106_READ_ONLY"


def test_mixed_schema_rejected_without_rewrite():
    altered = replace_member(
        kmz(), "wpmz/template.kml",
        lambda body: body.replace(WPML_NS.encode(), b"http://www.dji.com/wpmz/1.0.6"),
    )
    result = audit_kmz(altered)
    assert result["status"] == "unsupported"
    assert "MIXED_WPML_SCHEMAS" in {i["code"] for i in result["findings"]}


def test_modified_camera_lens_refused_even_if_xml_well_formed():
    data = replace_member(
        kmz(), "wpmz/waylines.wpml",
        lambda body: body.replace(b"<wpml:payloadLensIndex>wide</wpml:payloadLensIndex>",
                                  b"<wpml:payloadLensIndex>ir</wpml:payloadLensIndex>"),
    )
    result = audit_kmz(data)
    assert result["status"] == "unsupported"
    assert result["editable_in_aeronexus"] is False
    assert result["findings"][0]["code"] == "OUTSIDE_CANONICAL_EDITABLE_SUBSET"


def test_foreign_action_is_not_reinterpreted_as_supported():
    data = replace_member(
        kmz(), "wpmz/waylines.wpml",
        lambda body: body.replace(
            b"<wpml:actionActuatorFunc>startRecord</wpml:actionActuatorFunc>",
            b"<wpml:actionActuatorFunc>startSmartOblique</wpml:actionActuatorFunc>",
        ),
    )
    report = audit_kmz(data)
    assert report["status"] == "unsupported"
    assert "startSmartOblique" not in json.dumps(report)


def test_dtd_and_duplicate_zip_members_are_rejected():
    data = replace_member(
        kmz(), "wpmz/template.kml",
        lambda body: b"<!DOCTYPE x [<!ENTITY test 'value'>]>" + body,
    )
    assert "XML_DTD_NOT_ALLOWED" in {x["code"] for x in audit_kmz(data)["findings"]}
    dest = BytesIO()
    with ZipFile(dest, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("wpmz/template.kml", b"first")
        with pytest.warns(UserWarning, match="Duplicate name"):
            archive.writestr("wpmz/template.kml", b"second")
    assert "DUPLICATE_ZIP_MEMBER" in {
        x["code"] for x in audit_kmz(dest.getvalue())["findings"]
    }


def test_cli_is_read_only_and_does_not_print_path_or_mission_content(tmp_path, capsys):
    path = tmp_path / "private-mission.kmz"
    path.write_bytes(kmz())
    assert main([str(path)]) == 0
    out = capsys.readouterr().out
    assert json.loads(out)["status"] == "supported_subset"
    assert "private-mission" not in out
    assert "PRIVATE_NAME_MUST_NOT_LEAK" not in out


def test_complete_default_heading_path_avoids_interop_advisory():
    report = audit_kmz(kmz())
    assert report["editable_in_aeronexus"]
    assert "HEADING_PATH_MODE_INTEROP_UNVERIFIED" not in {
        x["code"] for x in report["findings"]
    }
    assert report["full_dji_wpml_conformance_verified"] is False
