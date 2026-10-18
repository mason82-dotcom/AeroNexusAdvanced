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
        "camera_lens": 1, "focus": 1, "gimbal": 1, "media_naming": 1,
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
        "camera_lens": 1,
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
        "actions_with_field": 2, "multiplicity_per_action": {"1": 2},
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


def test_repeated_field_name_is_counted_per_action_without_leaking_values():
    once = param_archive(unknown_tag=True)
    repeated = with_substituted_action(
        once, "<wpml:vendorSecretTag>NEVER-EXPOSE-ABC789</wpml:vendorSecretTag>",
        "<wpml:vendorSecretTag>NEVER-EXPOSE-ABC789</wpml:vendorSecretTag>"
        "<wpml:vendorSecretTag>ANOTHER-PRIVATE-VALUE</wpml:vendorSecretTag>")
    info = av._aggregate_action_records([
        (1, once), (2, repeated)
    ], parameter_hints=True, field_aliases=True)
    assert info["unknown_field_aliases"] == [{
        "id": "P01", "occurrences": 3, "file_count": 2,
        "action_aliases": ["A01"], "actions_with_field": 2,
        "multiplicity_per_action": {"1": 1, "2": 1},
    }]
    assert info["anonymous_types"][0]["unknown_field_alias_counts"] == {"P01": 3}
    output = json.dumps(info)
    assert "vendorSecretTag" not in output
    assert "ANOTHER-PRIVATE-VALUE" not in output
    assert info["full_content_verified"] is False
    assert info["flight_compatibility_verified"] is False


def test_route_scoped_field_multiplicity_matches_library_totals():
    once = param_archive(unknown_tag=True)
    repeated = with_substituted_action(
        once, "<wpml:vendorSecretTag>NEVER-EXPOSE-ABC789</wpml:vendorSecretTag>",
        "<wpml:vendorSecretTag>NEVER-EXPOSE-ABC789</wpml:vendorSecretTag>"
        "<wpml:vendorSecretTag>ANOTHER-PRIVATE-VALUE</wpml:vendorSecretTag>")
    result = av._aggregate_action_records(
        [(1, once), (2, repeated)],
        parameter_hints=True, field_aliases=True)
    assert result["results"][0]["unknown_field_multiplicity_by_route"] == [
        {"P01": {"1": 1}}
    ]
    assert result["results"][1]["unknown_field_multiplicity_by_route"] == [
        {"P01": {"2": 1}}
    ]
    total = sum(
        int(mult) * occurrences
        for item in result["results"]
        for route in item["unknown_field_multiplicity_by_route"]
        for counts in route.values()
        for mult, occurrences in counts.items()
    )
    assert total == 3
    assert result["unknown_field_aliases"][0]["occurrences"] == total
    serialized = json.dumps(result)
    assert "vendorSecretTag" not in serialized
    assert "ANOTHER-PRIVATE-VALUE" not in serialized
    assert result["full_content_verified"] is False


def test_default_action_report_does_not_expose_route_field_multiplicity():
    out = av._aggregate_action_records([(1, param_archive(unknown_tag=True))])
    assert "unknown_field_multiplicity_by_route" not in out["results"][0]
    out = av._aggregate_action_records(
        [(1, param_archive(unknown_tag=True))], parameter_hints=True)
    assert "unknown_field_multiplicity_by_route" not in out["results"][0]


def test_xml_position_bucket_divides_six_placemark_anchors_without_coordinates():
    mission = WaypointMission.model_validate({
        "name": "HIGHLY-PRIVATE-ROUTE", "drone_model": "mavic3e",
        "waypoints": [
            {"latitude": 49.10 + i * 0.01, "longitude": 8.5,
             "take_photo": True}
            for i in range(6)
        ],
    })
    raw = export_kmz(mission, timestamp_ms=1730000000000)
    buf = BytesIO()
    with ZipFile(BytesIO(raw)) as src, ZipFile(buf, "w") as dst:
        for filename in src.namelist():
            data = src.read(filename)
            if filename == "wpmz/waylines.wpml":
                data = data.replace(
                    b"<wpml:actionActuatorFunc>takePhoto</wpml:actionActuatorFunc>",
                    b"<wpml:actionActuatorFunc>secretVendorAction</wpml:actionActuatorFunc>")
                data = data.replace(
                    b"<wpml:actionActuatorFuncParam>",
                    b"<wpml:actionActuatorFuncParam>"
                    b"<wpml:privateDiagnosticField>NEVER-LOG</wpml:privateDiagnosticField>")
            dst.writestr(filename, data)
    result = av._aggregate_action_records(
        [(1, buf.getvalue())],
        parameter_hints=True, field_aliases=True, position_buckets=True)
    assert result["results"][0]["unknown_field_xml_placement_by_route"] == [
        {"P01": {"first": {"1": 2}, "middle": {"1": 2}, "last": {"1": 2}}}
    ]
    assert result["unknown_field_aliases"][0]["occurrences"] == 6
    serialized = json.dumps(result)
    for private in ("HIGHLY-PRIVATE-ROUTE", "49.10", "secretVendorAction",
                    "privateDiagnosticField", "NEVER-LOG"):
        assert private not in serialized


def test_group_span_readonly_xml_classification_and_index_bounds():
    from xml.etree import ElementTree as ET
    from aeronexus.wpml_export import WPML_NS
    W = "{" + WPML_NS + "}"
    group = ET.Element(W + "actionGroup")
    waypoint = ET.Element(W + "Placemark")
    ET.SubElement(waypoint, W + "index").text = "1"
    ET.SubElement(group, W + "actionGroupStartIndex").text = "1"
    ET.SubElement(group, W + "actionGroupEndIndex").text = "1"
    assert av._group_xml_span_relation(group, waypoint, W) == "single_at_anchor"
    group.find(W + "actionGroupEndIndex").text = "3"
    assert av._group_xml_span_relation(group, waypoint, W) == "range_starts_at_anchor"
    group.find(W + "actionGroupStartIndex").text = "2"
    assert av._group_xml_span_relation(group, waypoint, W) == "range_starts_elsewhere"
    group.find(W + "actionGroupEndIndex").text = "2"
    assert av._group_xml_span_relation(group, waypoint, W) == "single_elsewhere"
    group.find(W + "actionGroupEndIndex").text = "1"
    assert av._group_xml_span_relation(group, waypoint, W) == "reversed_span"
    group.find(W + "actionGroupEndIndex").text = "65536"
    assert av._group_xml_span_relation(group, waypoint, W) == "missing_or_invalid_span"
    group.find(W + "actionGroupEndIndex").text = "3"
    waypoint.find(W + "index").text = "private-location-SECRET"
    assert av._group_xml_span_relation(group, waypoint, W) == "unresolved_placemark_index"


def test_span_audit_classifies_group_status_without_leaking_indices():
    # Synthetic AeroNexus fixture exports a same-index reachPoint action
    # group, but the anonymous actuator name remains untrusted.
    raw = archive("privateUnusedActuator", version="1.0.6")
    with_field = with_substituted_action(
        raw,
        "<wpml:actionActuatorFuncParam>",
        "<wpml:actionActuatorFuncParam><wpml:secretField>NEVER-EXPOSE-ME</wpml:secretField>",
    )
    report = av._aggregate_action_records(
        [(1, with_field)], parameter_hints=True,
        field_aliases=True, span_audit=True)
    assert report["results"][0]["unknown_field_xml_span_by_route"] == [
        {"P01": {"single_at_anchor": 1}},
    ]
    assert report["unknown_field_aliases"][0]["actions_with_field"] == 1
    assert "single_at_anchor" in json.dumps(report)
    for sensitive in ("privateUnusedActuator", "secretField", "NEVER-EXPOSE-ME"):
        assert sensitive not in json.dumps(report)
    assert report["flight_compatibility_verified"] is False


def test_span_audit_range_not_confused_with_anchor_or_execution():
    raw = archive("secretCompanyActuator")
    modified = with_substituted_action(
        raw,
        "<wpml:actionGroupEndIndex>0</wpml:actionGroupEndIndex>",
        "<wpml:actionGroupEndIndex>1</wpml:actionGroupEndIndex>",
    )
    modified = with_substituted_action(
        modified,
        "<wpml:actionActuatorFuncParam>",
        "<wpml:actionActuatorFuncParam><wpml:otherPrivateField>PRIVATE-ABC</wpml:otherPrivateField>",
    )
    report = av._aggregate_action_records(
        [(1, modified)], parameter_hints=True,
        field_aliases=True, span_audit=True)
    assert report["results"][0]["unknown_field_xml_span_by_route"] == [
        {"P01": {"range_starts_at_anchor": 1}},
    ]
    assert "PRIVATE-ABC" not in json.dumps(report)


def test_xml_index_delta_categories_and_out_of_folder_are_not_flight_distances():
    from xml.etree import ElementTree as ET
    from aeronexus.wpml_export import WPML_NS
    W = "{" + WPML_NS + "}"
    group = ET.Element(W + "actionGroup")
    place = ET.Element(W + "Placemark")
    ET.SubElement(group, W + "actionGroupStartIndex").text = "0"
    end = ET.SubElement(group, W + "actionGroupEndIndex")
    ET.SubElement(place, W + "index").text = "0"
    indexes = set(range(30))
    cases = {
        0: "same_index",
        1: "one_index_step",
        2: "two_to_four_index_steps",
        4: "two_to_four_index_steps",
        5: "five_to_sixteen_index_steps",
        16: "five_to_sixteen_index_steps",
        17: "over_sixteen_index_steps",
        29: "over_sixteen_index_steps",
    }
    for length, expected in cases.items():
        end.text = str(length)
        assert av._group_xml_index_delta_bucket(group, place, W, indexes) == expected
    end.text = "30"
    assert av._group_xml_index_delta_bucket(
        group, place, W, indexes) == "endpoint_outside_folder"
    end.text = "9"
    assert av._group_xml_index_delta_bucket(
        group, place, W, None) == "unreliable_folder_indices"
    group.find(W + "actionGroupStartIndex").text = "1"
    assert av._group_xml_index_delta_bucket(
        group, place, W, indexes) == "starts_elsewhere"
    group.find(W + "actionGroupStartIndex").text = "10"
    assert av._group_xml_index_delta_bucket(
        group, place, W, indexes) == "reversed_span"
    end.text = "private-secret"
    assert av._group_xml_index_delta_bucket(
        group, place, W, indexes) == "missing_or_invalid_index"


def test_span_length_buckets_report_only_categories_and_p_field_multiplicity():
    base = archive("privateCorpAction", version="1.0.6")
    altered = with_substituted_action(
        base, "<wpml:actionGroupEndIndex>0</wpml:actionGroupEndIndex>",
        "<wpml:actionGroupEndIndex>1</wpml:actionGroupEndIndex>")
    altered = with_substituted_action(
        altered, "<wpml:actionActuatorFuncParam>",
        "<wpml:actionActuatorFuncParam>"
        "<wpml:customSecretField>CLASSIFIED-ONE</wpml:customSecretField>"
        "<wpml:customSecretField>CLASSIFIED-TWO</wpml:customSecretField>")
    result = av._aggregate_action_records(
        [(1, altered)], parameter_hints=True, field_aliases=True,
        span_audit=True, span_length_buckets=True)
    report = result["results"][0]
    assert report["unknown_field_xml_index_delta_by_route"] == [
        {"P01": {"one_index_step": {"2": 1}}}]
    assert report["unknown_field_xml_span_by_route"] == [
        {"P01": {"range_starts_at_anchor": 1}}]
    assert result["unknown_field_aliases"][0]["occurrences"] == 2
    data = json.dumps(result)
    for secret in ("privateCorpAction", "customSecretField",
                   "CLASSIFIED-ONE", "CLASSIFIED-TWO"):
        assert secret not in data
    assert result["full_content_verified"] is False
    assert result["flight_compatibility_verified"] is False


def test_span_length_bucket_is_explicit_opt_in():
    data = param_archive(unknown_tag=True)
    with pytest.raises(ValueError, match="require span audit"):
        av._aggregate_action_records(
            [(1, data)], parameter_hints=True, field_aliases=True,
            span_length_buckets=True)
    old = av._aggregate_action_records(
        [(1, data)], parameter_hints=True, field_aliases=True,
        span_audit=True)
    assert "unknown_field_xml_index_delta_by_route" not in old["results"][0]


def test_span_audit_opt_in_only():
    with pytest.raises(ValueError, match="span audit requires field aliases"):
        av._aggregate_action_records(
            [(1, archive())], parameter_hints=True, span_audit=True)
    data = av._aggregate_action_records(
        [(1, param_archive(unknown_tag=True))], parameter_hints=True,
        field_aliases=True)
    assert "unknown_field_xml_span_by_route" not in data["results"][0]


def test_position_buckets_require_field_aliases_and_are_off_by_default():
    with pytest.raises(ValueError, match="require field aliases"):
        av._aggregate_action_records(
            [(1, param_archive(unknown_tag=True))],
            parameter_hints=True, position_buckets=True)
    result = av._aggregate_action_records(
        [(1, param_archive(unknown_tag=True))],
        parameter_hints=True, field_aliases=True)
    assert "unknown_field_xml_placement_by_route" not in result["results"][0]


def test_first_last_bucket_for_two_placemarks():
    assert av._xml_placement_bucket(0, 2) == "first"
    assert av._xml_placement_bucket(1, 2) == "last"
    assert av._xml_placement_bucket(0, 1) == "first"
    with pytest.raises(LocalWaylineError, match="unsupported_geometry"):
        av._xml_placement_bucket(1, 1)


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
    assert entry["parameter_category_counts"] == {"camera_lens": 1, "media_naming": 1, "payload": 1}


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



@pytest.mark.parametrize("action_name", [
    "setFocusType", "startSmartOblique", "stopSmartOblique",
    "startContinuousShooting", "stopContinuousShooting",
    "startTimeLapse", "stopTimeLapse",
])
def test_observed_pilot2_enum_is_named_but_not_claimed_documented(action_name):
    report = av._aggregate_action_records([
        (1, archive(action_name, version="1.0.6")),
    ])
    assert report["recognized_action_total"] == 0
    assert report["unknown_action_total"] == 1  # legacy non-documented metric
    assert report["identified_action_total"] == 1
    assert report["unresolved_action_total"] == 0
    assert report["identified_types"] == [{
        "name": action_name, "alias": "A01",
        "occurrences": 1, "file_count": 1,
    }]
    assert report["full_content_verified"] is False
    assert report["flight_compatibility_verified"] is False


def test_mixed_observed_and_unrecognized_actions_stay_separate_and_private():
    report = av._aggregate_action_records([
        (1, archive("startSmartOblique", version="1.0.6")),
        (2, archive("genuinelyPrivateEnum", version="1.0.6")),
    ])
    assert report["identified_action_total"] == 1
    assert report["unresolved_action_total"] == 1
    assert report["unknown_action_total"] == 2
    assert "genuinelyPrivateEnum" not in json.dumps(report)



def test_documented_types_are_counted_without_marking_flight_compatibility():
    report = av._aggregate_action_records([
        (1, archive("takePhoto")),
        (2, archive("startRecord", version="1.0.6")),
        (3, archive("stopRecord", version="1.0.6")),
    ])
    assert report["documented_type_counts"] == {
        "startRecord": 1, "stopRecord": 1, "takePhoto": 1,
    }
    assert report["recognized_action_total"] == 3
    assert report["identified_action_total"] == 0
    assert report["full_content_verified"] is False
    assert report["flight_compatibility_verified"] is False



def test_observed_pilot2_fields_are_presence_only_not_generic_unknown_names():
    raw = archive("startSmartOblique", version="1.0.6")
    extra = (
        b"<wpml:smartObliqueCycleMode>PRIVATE-VALUE</wpml:smartObliqueCycleMode>"
        b"<wpml:smartObliquePoint>PRIVATE-COORDINATE</wpml:smartObliquePoint>"
        b"<wpml:smartObliquePoint>PRIVATE-SECOND</wpml:smartObliquePoint>"
    )
    changed = BytesIO()
    with ZipFile(BytesIO(raw)) as src, ZipFile(changed, "w") as dst:
        for filename in src.namelist():
            content = src.read(filename)
            if filename == "wpmz/waylines.wpml":
                content = content.replace(
                    b"<wpml:actionActuatorFuncParam>",
                    b"<wpml:actionActuatorFuncParam>" + extra, 1)
            dst.writestr(filename, content)
    output = av._aggregate_action_records(
        [(1, changed.getvalue())], parameter_hints=True, field_aliases=True)
    one = output["anonymous_types"][0]
    assert one["parameter_category_counts"]["pilot2_smart_oblique_unverified"] == 1
    assert "unclassified_fields_present" not in one["parameter_category_counts"]
    assert output["unknown_field_aliases"] == []
    encoded = json.dumps(output)
    for secret in ("PRIVATE-VALUE", "PRIVATE-COORDINATE", "PRIVATE-SECOND"):
        assert secret not in encoded
    assert output["flight_compatibility_verified"] is False
