"""Privacy regression tests for read-only Pilot 2 unknown-action correlation."""
import asyncio
from io import BytesIO
import json
from zipfile import ZipFile

import pytest

from aeronexus import pilot2_wayline_action_vocabulary as av
from aeronexus.local_waylines import Credentials, LocalWaylineError
from aeronexus.wpml_export import WaypointMission, export_kmz


WORKSPACE = "12345678-1234-4234-8234-123456789012"
A = "00000000-0000-0000-0000-000000000011"
B = "00000000-0000-0000-0000-000000000012"
CREDS = Credentials(WORKSPACE, "very-sensitive-test-credential")


def archive(name="takePhoto", *, version="1.0.2", with_start=False):
    m = WaypointMission.model_validate({
        "name": "Private inspection route", "drone_model": "mavic3e",
        "waypoints": [
            {"latitude": 49.12, "longitude": 8.5, "take_photo": True},
            {"latitude": 49.13, "longitude": 8.6, "take_photo": False},
        ],
    })
    raw = export_kmz(m, timestamp_ms=1730000000000)
    buf = BytesIO()
    with ZipFile(BytesIO(raw)) as original, ZipFile(buf, "w") as modified:
        for filename in original.namelist():
            content = original.read(filename)
            if filename == "wpmz/waylines.wpml":
                content = content.replace(
                    b"<wpml:actionActuatorFunc>takePhoto</wpml:actionActuatorFunc>",
                    ("<wpml:actionActuatorFunc>" + name
                     + "</wpml:actionActuatorFunc>").encode(),
                )
                if with_start:
                    content = content.replace(
                        b"<Folder>",
                        (b"<Folder><wpml:startActionGroup><wpml:action>"
                         b"<wpml:actionActuatorFunc>" + name.encode()
                         + b"</wpml:actionActuatorFunc></wpml:action>"
                         + b"</wpml:startActionGroup>"),
                    )
                if version != "1.0.2":
                    content = content.replace(
                        b"http://www.dji.com/wpmz/1.0.2",
                        ("http://www.dji.com/wpmz/" + version).encode(),
                    )
            modified.writestr(filename, content)
    return buf.getvalue()


def test_ephemeral_alias_correlates_same_unknown_from_multiple_archives():
    report = av._aggregate_action_records([
        (1, archive("secret-action-A", with_start=True)),
        (2, archive("secret-action-A", version="1.0.6")),
        (3, archive("secret-action-B")),
    ])
    assert report["unknown_action_total"] == 4
    assert report["recognized_action_total"] == 0
    assert report["anonymous_types"] == [
        {
            "id": "A01", "occurrences": 3, "file_count": 2,
            "location_counts": {"start": 1, "waypoint": 2},
            "trigger_counts": {"reachPoint": 2, "start": 1},
        },
        {
            "id": "A02", "occurrences": 1, "file_count": 1,
            "location_counts": {"waypoint": 1},
            "trigger_counts": {"reachPoint": 1},
        },
    ]
    assert report["results"][0]["unknown_alias_counts_by_route"] == [{"A01": 2}]
    assert report["results"][1]["unknown_alias_counts_by_route"] == [{"A01": 1}]
    assert report["results"][2]["unknown_alias_counts_by_route"] == [{"A02": 1}]
    output = json.dumps(report)
    for secret in ["secret-action-A", "secret-action-B", "Private inspection",
                   "49.12", "8.5,", CREDS.access_token, WORKSPACE, A, B]:
        assert secret not in output
    assert report["full_content_verified"] is False
    assert report["flight_compatibility_verified"] is False


def param_archive(*, unknown_tag=False, nonstandard_ns=False):
    raw = archive("privateActionNeverExpose", version="1.0.6")
    source = b"<wpml:actionActuatorFuncParam>"
    extra = (b"<wpml:gimbalPitchRotateAngle>TOP-SECRET-VALUE</wpml:gimbalPitchRotateAngle>"
             b"<wpml:focusX>DO-NOT-LEAK</wpml:focusX>")
    if unknown_tag:
        extra += b"<wpml:vendorSecretTag>NEVER-EXPOSE-ABC789</wpml:vendorSecretTag>"
    if nonstandard_ns:
        extra += b"<foreign xmlns='urn:unsafe'>hidden-text</foreign>"
    target = source + extra
    result = BytesIO()
    with ZipFile(BytesIO(raw)) as src, ZipFile(result, "w") as dst:
        for path in src.namelist():
            data = src.read(path)
            if path == "wpmz/waylines.wpml":
                assert source in data
                data = data.replace(source, target, 1)
            dst.writestr(path, data)
    return result.getvalue()


def test_optional_parameter_hints_classify_only_static_fields_without_values():
    data = param_archive(unknown_tag=True, nonstandard_ns=True)
    report = av._aggregate_action_records([(1, data)], parameter_hints=True)
    entry = report["anonymous_types"][0]
    assert entry["id"] == "A01"
    assert entry["occurrences"] == 1
    assert entry["parameter_container_counts"] == {"present": 1}
    assert entry["parameter_category_counts"] == {
        "focus": 1, "gimbal": 1, "media_naming": 1,
        "payload": 1, "unclassified_fields_present": 1}
    encoded = json.dumps(report)
    for secret in ("TOP-SECRET-VALUE", "DO-NOT-LEAK", "NEVER-EXPOSE-ABC789",
                   "hidden-text", "privateActionNeverExpose", "vendorSecretTag"):
        assert secret not in encoded
    assert report["full_content_verified"] is False
    assert report["flight_compatibility_verified"] is False


def test_official_additional_fields_are_presence_only_and_never_leak_values():
    raw = archive("secretM3EAction", version="1.0.6")
    fields = (
        b"<wpml:actionUUID>PRIVATE-UUID-456</wpml:actionUUID>"
        b"<wpml:orientedFilePath>/private/photos/location.jpg</wpml:orientedFilePath>"
        b"<wpml:gimbalPort>PRIVATE-PORT</wpml:gimbalPort>"
        b"<wpml:focalLength>PRIVATE-FOCAL</wpml:focalLength>"
        b"<wpml:imageWidth>PRIVATE-DIMENSION</wpml:imageWidth>"
        b"<wpml:orientedCameraType>PRIVATE-CAMERA</wpml:orientedCameraType>"
        b"<wpml:AFPos>PRIVATE-FOCUS</wpml:AFPos>"
        b"<wpml:gimbalRollRotateAngle>PRIVATE-GIMBAL</wpml:gimbalRollRotateAngle>"
    )
    output = BytesIO()
    with ZipFile(BytesIO(raw)) as src, ZipFile(output, "w") as dst:
        for file_name in src.namelist():
            data = src.read(file_name)
            if file_name == "wpmz/waylines.wpml":
                data = data.replace(b"<wpml:actionActuatorFuncParam>",
                                    b"<wpml:actionActuatorFuncParam>" + fields, 1)
            dst.writestr(file_name, data)
    result = av._aggregate_action_records(
        [(1, output.getvalue())], parameter_hints=True)
    category_counts = result["anonymous_types"][0]["parameter_category_counts"]
    assert category_counts == {
        "action_tracking": 1,
        "camera_model": 1,
        "focus": 1,
        "gimbal": 1,
        "image_dimensions": 1,
        "media_naming": 1,
        "media_reference": 1,
        "payload": 1,
        "zoom": 1,
    }
    encoded = json.dumps(result)
    for sensitive in ("PRIVATE-UUID-456", "/private/photos/location.jpg",
                      "PRIVATE-PORT", "PRIVATE-FOCAL", "PRIVATE-DIMENSION",
                      "PRIVATE-CAMERA", "PRIVATE-FOCUS", "PRIVATE-GIMBAL",
                      "secretM3EAction"):
        assert sensitive not in encoded
    assert result["full_content_verified"] is False
    assert result["flight_compatibility_verified"] is False


def with_substituted_action(data, old, new):
    dest = BytesIO()
    with ZipFile(BytesIO(data)) as src, ZipFile(dest, "w") as out:
        for path in src.namelist():
            content = src.read(path)
            if path == "wpmz/waylines.wpml":
                assert old.encode() in content
                content = content.replace(old.encode(), new.encode())
            out.writestr(path, content)
    return dest.getvalue()


def test_field_aliases_correlate_unknown_tag_across_two_unknown_actions():
    a = param_archive(unknown_tag=True, nonstandard_ns=True)
    b = with_substituted_action(
        param_archive(unknown_tag=True), "privateActionNeverExpose",
        "privateActionDifferent")
    report = av._aggregate_action_records(
        [(1, a), (2, b)], parameter_hints=True, field_aliases=True)
    assert report["anonymous_types"][0]["unknown_field_alias_counts"] == {"P01": 1}
    assert report["anonymous_types"][1]["unknown_field_alias_counts"] == {"P01": 1}
    assert report["anonymous_types"][0]["foreign_namespace_field_count"] == 1
    assert report["anonymous_types"][1]["foreign_namespace_field_count"] == 0
    assert report["unknown_field_aliases"] == [{
        "id": "P01", "occurrences": 2,
        "file_count": 2, "action_aliases": ["A01", "A02"],
    }]
    assert report["field_alias_scope"] == "single_invocation_only"
    encoded = json.dumps(report)
    for secret in (
        "vendorSecretTag", "TOP-SECRET-VALUE", "NEVER-EXPOSE-ABC789",
        "privateActionNeverExpose", "privateActionDifferent",
        "urn:unsafe", "hidden-text",
    ):
        assert secret not in encoded
    assert report["full_content_verified"] is False


def test_field_aliases_require_explicit_parameter_hints():
    with pytest.raises(ValueError, match="require parameter hints"):
        av._aggregate_action_records(
            [(1, param_archive(unknown_tag=True))], field_aliases=True)


def test_field_alias_limit_fails_closed(monkeypatch):
    monkeypatch.setattr(av, "MAX_FIELD_ALIASES", 0)
    with pytest.raises(LocalWaylineError, match="unsupported_geometry"):
        av._aggregate_action_records(
            [(1, param_archive(unknown_tag=True))],
            parameter_hints=True, field_aliases=True)


def test_without_field_aliases_no_private_field_correlation_output():
    report = av._aggregate_action_records(
        [(1, param_archive(unknown_tag=True))], parameter_hints=True)
    assert "unknown_field_aliases" not in report
    assert "field_alias_scope" not in report
    assert "unknown_field_alias_counts" not in report["anonymous_types"][0]


def test_parameter_hints_off_keeps_existing_response_shape():
    report = av._aggregate_action_records([(1, param_archive())])
    entry = report["anonymous_types"][0]
    assert "parameter_container_counts" not in entry
    assert "parameter_category_counts" not in entry


def test_parameter_hints_include_absent_start_action_container():
    report = av._aggregate_action_records(
        [(1, archive("privateCode", with_start=True))], parameter_hints=True)
    entry = report["anonymous_types"][0]
    assert entry["parameter_container_counts"] == {"absent": 1, "present": 1}
    assert entry["parameter_category_counts"] == {"media_naming": 1, "payload": 1}


def test_parameter_field_fanout_fails_closed():
    raw = archive("privateCode")
    extra = b"".join(b"<wpml:x/>" for _ in range(av.MAX_PARAM_FIELDS_PER_ACTION + 1))
    result = BytesIO()
    with ZipFile(BytesIO(raw)) as src, ZipFile(result, "w") as dst:
        for path in src.namelist():
            data = src.read(path)
            if path == "wpmz/waylines.wpml":
                data = data.replace(b"<wpml:actionActuatorFuncParam>",
                                    b"<wpml:actionActuatorFuncParam>" + extra)
            dst.writestr(path, data)
    with pytest.raises(LocalWaylineError, match="invalid_archive"):
        av._archive_action_records(result.getvalue())


def test_recognized_actuator_is_not_aliased():
    report = av._aggregate_action_records([(1, archive())])
    assert report["unknown_action_total"] == 0
    assert report["recognized_action_total"] == 1
    assert report["anonymous_types"] == []
    assert report["results"][0]["unknown_alias_counts_by_route"] == [{}]


def test_reject_unknown_wpml_schema_without_leaking_xml():
    with pytest.raises(LocalWaylineError, match="unsupported_geometry"):
        av._archive_action_records(archive(version="1.0.9"))


def test_alias_cardinality_limit_fails_closed(monkeypatch):
    monkeypatch.setattr(av, "MAX_ALIASES", 1)
    with pytest.raises(LocalWaylineError, match="unsupported_geometry"):
        av._aggregate_action_records([(1, archive("customX")), (2, archive("customY"))])


def test_inventory_must_be_complete_and_match_workspace():
    requests = []
    async def inventory(_):
        return {"state": "connected", "workspace_id": WORKSPACE,
                "pagination_complete": False,
                "waylines": [{"wayline_id": A}]}
    async def downloader(_, id_value):
        requests.append(id_value)
        return archive()
    result = asyncio.run(av.diagnose_action_vocabulary(
        inventory_reader=inventory, kmz_reader=downloader,
        credentials_loader=lambda _: CREDS))
    assert result == {"inventory_state": "incomplete_inventory", "results": []}
    assert requests == []


def test_mock_live_reader_never_returns_wayline_id_or_token():
    calls = []
    async def inventory(_):
        return {"state": "connected", "workspace_id": WORKSPACE,
                "pagination_complete": True, "reported_total": 2,
                "waylines": [{"wayline_id": A}, {"wayline_id": B}]}
    async def reader(_, id_value):
        calls.append(id_value)
        return archive("privateMappingAction", version="1.0.6")
    data = asyncio.run(av.diagnose_action_vocabulary(
        inventory_reader=inventory, kmz_reader=reader,
        credentials_loader=lambda _: CREDS))
    assert calls == [A, B]
    assert data["inventory_state"] == "connected"
    assert data["checked"] == 2
    assert data["unknown_action_total"] == 2
    assert data["anonymous_types"][0]["file_count"] == 2
    encoded = json.dumps(data)
    for secret in (A, B, WORKSPACE, CREDS.access_token, "privateMappingAction"):
        assert secret not in encoded


def test_partial_bad_archive_reports_only_sanitized_index():
    async def inventory(_):
        return {"state": "connected", "workspace_id": WORKSPACE,
                "pagination_complete": True, "reported_total": 2,
                "waylines": [{"wayline_id": A}, {"wayline_id": B}]}
    async def download(_, ident):
        return archive("sharedAnon") if ident == A else b"password-SHOULD-NOT-LEAK"
    result = asyncio.run(av.diagnose_action_vocabulary(
        inventory_reader=inventory, kmz_reader=download,
        credentials_loader=lambda _: CREDS))
    assert result["checked"] == 2
    assert result["results"][1] == {"index": 2, "state": "unavailable_or_unsupported"}
    assert "password-SHOULD-NOT-LEAK" not in json.dumps(result)
