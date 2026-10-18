"""WPML waypoint KMZ exports: structure, profiles and safe validation."""
from io import BytesIO
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import pytest
from pydantic import ValidationError

from aeronexus.wpml_export import Waypoint, WaypointMission, export_kmz, import_kmz, waypoints_for_export, KML_NS, WPML_NS


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
    {"waypoints": [{"latitude": 0.0, "longitude": 0.0}]},
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


def test_own_kmz_import_round_trip():
    original = draft(name="Prüfrunde", description="Testflug offline")
    data = export_kmz(original, timestamp_ms=1760641200000)
    restored = import_kmz(data)
    assert restored.model_dump() == original.model_dump()


def test_forged_author_is_rejected():
    data = export_kmz(draft(), timestamp_ms=1760641200000)
    with ZipFile(BytesIO(data)) as source:
        template = source.read("wpmz/template.kml").replace(
            b"AeroNexusAdvanced", b"SomeOtherSoftware")
        waylines = source.read("wpmz/waylines.wpml")
    buffer = BytesIO()
    from zipfile import ZIP_DEFLATED
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as target:
        target.writestr("wpmz/template.kml", template)
        target.writestr("wpmz/waylines.wpml", waylines)
    with pytest.raises(ValueError, match="Only AeroNexus"):
        import_kmz(buffer.getvalue())


@pytest.mark.parametrize("payload", [b"", b"NOT-A-ZIP", b"x" * (2 * 1024 * 1024 + 1)])
def test_invalid_kmz_import_rejected(payload):
    with pytest.raises(ValueError):
        import_kmz(payload)


def test_import_rejects_unsupported_action():
    archive_bytes = export_kmz(draft(), timestamp_ms=1)
    with ZipFile(BytesIO(archive_bytes)) as source:
        template = source.read("wpmz/template.kml")
        route = source.read("wpmz/waylines.wpml").replace(b"takePhoto", b"startRecord")
    buffer = BytesIO()
    from zipfile import ZIP_DEFLATED
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as output:
        output.writestr("wpmz/template.kml", template)
        output.writestr("wpmz/waylines.wpml", route)
    with pytest.raises(ValueError, match="Unsupported waypoint action"):
        import_kmz(buffer.getvalue())


def closed_draft(**changes):
    """A route with four editable points and a fifth executed return point."""
    return draft(waypoints=[
        {"latitude": 49.1623682, "longitude": 8.5939103, "take_photo": True},
        {"latitude": 49.162372, "longitude": 8.595573},
        {"latitude": 49.163281, "longitude": 8.596909},
        {"latitude": 49.164732, "longitude": 8.595031},
    ], close_route=True, **changes)


def test_closed_route_exports_a_real_fifth_wpml_waypoint():
    mission = closed_draft()
    assert len(mission.waypoints) == 4
    assert len(waypoints_for_export(mission)) == 5
    template, waylines = files(mission)
    for root in (template, waylines):
        points = root.findall(".//" + K + "Placemark")
        assert len(points) == 5
        assert [p.find(W + "index").text for p in points] == [
            "0", "1", "2", "3", "4",
        ]
        assert points[4].find(".//" + K + "coordinates").text == (
            points[0].find(".//" + K + "coordinates").text
        )
        # The return leg reaches waypoint 1 but never repeats its photo action.
        assert points[0].find(".//" + W + "actionActuatorFunc").text == "takePhoto"
        assert points[4].find(".//" + W + "actionGroup") is None
    assert waylines.findall(".//" + K + "Placemark")[4].find(
        W + "executeHeight"
    ).text == "50"
    assert waylines.find(".//" + W + "finishAction").text == "goHome"


def test_closed_route_import_restores_reversible_checkbox():
    first = closed_draft()
    imported = import_kmz(export_kmz(first, timestamp_ms=10))
    assert imported.close_route is True
    assert imported.model_dump() == first.model_dump()
    # Re-export keeps the executed route closed and does not create 6 points.
    second_template, second_waylines = files(imported)
    assert len(second_template.findall(".//" + K + "Placemark")) == 5
    assert len(second_waylines.findall(".//" + K + "Placemark")) == 5


def test_switching_closed_route_off_eliminates_fifth_wpml_waypoint():
    first = closed_draft()
    original = first.model_copy(update={"close_route": False})
    assert len(first.waypoints) == len(original.waypoints) == 4
    template, route = files(original)
    assert len(route.findall(".//" + K + "Placemark")) == 4
    assert route.findall(".//" + K + "Placemark")[-1].find(
        ".//" + K + "coordinates"
    ).text != route.findall(".//" + K + "Placemark")[0].find(
        ".//" + K + "coordinates"
    ).text
    assert import_kmz(export_kmz(original, timestamp_ms=11)).close_route is False


def test_closed_route_with_existing_return_point_does_not_duplicate_point():
    mission = draft(close_route=True, waypoints=[
        {"latitude": 49.12, "longitude": 8.51},
        {"latitude": 49.13, "longitude": 8.52},
        {"latitude": 49.14, "longitude": 8.53},
        {"latitude": 49.12, "longitude": 8.51},
    ])
    assert len(waypoints_for_export(mission)) == 4
    _, route = files(mission)
    assert len(route.findall(".//" + K + "Placemark")) == 4
    imported = import_kmz(export_kmz(mission, timestamp_ms=12))
    assert imported.close_route is True
    assert len(imported.waypoints) == 3
    assert len(waypoints_for_export(imported)) == 4


def test_closed_route_rejects_fewer_than_three_distinct_points():
    mission = draft(close_route=True)
    with pytest.raises(ValueError, match="at least 3 distinct"):
        export_kmz(mission, timestamp_ms=13)
    mission = draft(close_route=True, waypoints=[
        {"latitude": 49.12, "longitude": 8.51},
        {"latitude": 49.13, "longitude": 8.52},
        {"latitude": 49.12, "longitude": 8.51},
    ])
    with pytest.raises(ValueError, match="at least 3 distinct"):
        export_kmz(mission, timestamp_ms=13)


def test_closed_route_enforces_500_total_executed_wpml_points():
    points = [
        {"latitude": round(49.1 + i * 0.00001, 7), "longitude": 8.6}
        for i in range(500)
    ]
    max_draft = draft(waypoints=points)
    assert len(waypoints_for_export(max_draft)) == 500
    # 500 editable points + actual final return = 501, never export this.
    max_closed = draft(close_route=True, waypoints=points)
    assert len(waypoints_for_export(max_closed)) == 501
    with pytest.raises(ValueError, match="between 2 and 500 executed"):
        export_kmz(max_closed, timestamp_ms=14)


def test_closed_route_requires_strict_boolean():
    with pytest.raises(ValidationError):
        draft(close_route="true")


@pytest.mark.parametrize("model,values", [
    ("mavic3e", (77, 0, 66, 0)), ("mavic3t", (77, 1, 67, 0)),
    ("mavic3m", (77, 2, 68, 0)), ("mavic3ta", (77, 3, 129, 0)),
    ("matrice4e", (99, 0, 88, 0)), ("matrice4t", (99, 1, 89, 0)),
])
def test_all_mission_profiles_preserve_aircraft_payload_and_actions(model, values):
    original = closed_draft(drone_model=model)
    data = export_kmz(original, timestamp_ms=123)
    for root in files(original):
        for tag, expected in zip(("droneEnumValue", "droneSubEnumValue", "payloadEnumValue", "payloadSubEnumValue"), values):
            assert root.find(".//" + W + tag).text == str(expected)
    assert import_kmz(data).model_dump() == original.model_dump()


def mutated_kmz(member, mutate):
    data = export_kmz(draft(), timestamp_ms=123)
    output = BytesIO()
    with ZipFile(BytesIO(data)) as source, ZipFile(output, "w") as target:
        for path in source.namelist():
            root = ET.fromstring(source.read(path))
            if path == member:
                mutate(root)
            target.writestr(path, ET.tostring(root))
    return output.getvalue()


@pytest.mark.parametrize("member,tag,value", [
    ("waylines.wpml", "globalRTHHeight", "100"),
    ("template.kml", "globalRTHHeight", "100"),
    ("waylines.wpml", "waypointSpeed", "12"),
    ("template.kml", "autoFlightSpeed", "12"),
    ("template.kml", "droneSubEnumValue", "0"),
    ("template.kml", "takeOffSecurityHeight", "70"),
    ("waylines.wpml", "exitOnRCLost", "goContinue"),
    ("template.kml", "exitOnRCLost", "goContinue"),
    ("waylines.wpml", "waypointHeadingMode", "fixed"),
    ("waylines.wpml", "waypointTurnDampingDist", "5"),
    ("waylines.wpml", "payloadPositionIndex", "1"),
    ("template.kml", "useGlobalSpeed", "0"),
    ("template.kml", "gimbalPitchAngle", "-90"),
    ("template.kml", "coordinateMode", "EGM96"),
    ("waylines.wpml", "actionTriggerType", "betweenAdjacentPoints"),
    ("waylines.wpml", "actionGroupEndIndex", "1"),
    ("waylines.wpml", "fileSuffix", "changed"),
])
def test_import_rejects_every_unrepresentable_setting(member, tag, value):
    def mutate(root):
        root.find(".//" + W + tag).text = value
    with pytest.raises(ValueError):
        import_kmz(mutated_kmz("wpmz/" + member, mutate))


@pytest.mark.parametrize("variant", ["duplicate_config", "unknown_action_param", "attribute", "extra_folder"])
def test_import_rejects_extra_or_ambiguous_structure(variant):
    from copy import deepcopy
    def mutate(root):
        doc = root.find(K + "Document")
        if variant == "duplicate_config":
            doc.append(deepcopy(doc.find(W + "missionConfig")))
        elif variant == "unknown_action_param":
            ET.SubElement(root.find(".//" + W + "actionActuatorFuncParam"), W + "useGlobalPayloadLensIndex").text = "0"
        elif variant == "attribute":
            doc.set("unknown", "value")
        else:
            ET.SubElement(doc, K + "Folder")
    with pytest.raises(ValueError):
        import_kmz(mutated_kmz("wpmz/waylines.wpml", mutate))


def test_import_allows_pretty_print_and_independent_creation_times():
    def mutate(root):
        root.find(".//" + W + "createTime").text = "100"
        root.find(".//" + W + "updateTime").text = "200"
        ET.indent(root)
    assert import_kmz(mutated_kmz("wpmz/template.kml", mutate)).model_dump() == draft().model_dump()


@pytest.mark.parametrize("model,lens,global_flag", [
    ("matrice4e", "wide", "0"),
    ("matrice4t", "wide", "0"),
    ("mavic3e", None, "0"),
    ("mavic3t", None, "0"),
    ("mavic3m", None, "0"),
])
def test_camera_action_lens_fields_follow_current_dji_matrix(model, lens, global_flag):
    """Validate both WPML documents, not just the executable route."""
    mission = draft(drone_model=model, waypoints=[
        {"latitude": 49.1, "longitude": 8.5, "take_photo": True,
         "actions": [{"type": "startRecord"}]},
        {"latitude": 49.2, "longitude": 8.6,
         "actions": [{"type": "stopRecord"}]},
    ])
    for document in files(mission):
        first = document.findall(".//" + K + "Placemark")[0]
        actions = {
            group.findtext(W + "action/" + W + "actionActuatorFunc"):
                group.find(W + "action/" + W + "actionActuatorFuncParam")
            for group in first.findall(W + "actionGroup")
        }
        assert set(actions) == {"takePhoto", "startRecord"}
        for operation in ("takePhoto", "startRecord"):
            params = actions[operation]
            assert params.findtext(W + "payloadPositionIndex") == "0"
            assert params.findtext(W + "payloadLensIndex") == lens
            assert params.findtext(W + "useGlobalPayloadLensIndex") == global_flag
        # DJI does not document these two fields as mandatory for stopRecord.
        second = document.findall(".//" + K + "Placemark")[1]
        stop = second.find(".//" + W + "actionActuatorFuncParam")
        assert stop is not None
        assert stop.find(W + "payloadLensIndex") is None
        assert stop.find(W + "useGlobalPayloadLensIndex") is None


def test_mavic3ta_not_inferred_to_support_matrice4_lens_fields():
    # M3TA is not independently documented in DJI's relevant WPML action rows.
    for document in files(draft(drone_model="mavic3ta")):
        params = document.find(".//" + W + "actionActuatorFuncParam")
        assert params is not None
        assert params.find(W + "payloadLensIndex") is None
        assert params.find(W + "useGlobalPayloadLensIndex") is None


def _previous_aeronexus_camera_kmz(mission):
    """A byte-structured fixture of the prior AeroNexus camera action writer."""
    from aeronexus.wpml_export import _xml
    from zipfile import ZIP_DEFLATED
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("wpmz/template.kml", _xml(
            mission, template=True, timestamp_ms=1760641200000,
            legacy_camera_params=True))
        archive.writestr("wpmz/waylines.wpml", _xml(
            mission, template=False, timestamp_ms=1760641200000,
            legacy_camera_params=True))
    return output.getvalue()


@pytest.mark.parametrize("model", ["matrice4e", "matrice4t", "mavic3e", "mavic3t", "mavic3m"])
def test_previous_aeronexus_kmz_camera_actions_import_and_upgrade(model):
    mission = draft(drone_model=model, waypoints=[
        {"latitude": 49.1, "longitude": 8.5, "take_photo": True,
         "actions": [{"type": "startRecord"}]},
        {"latitude": 49.2, "longitude": 8.6,
         "actions": [{"type": "stopRecord"}]},
    ])
    restored = import_kmz(_previous_aeronexus_camera_kmz(mission))
    assert restored.model_dump() == mission.model_dump()
    # An imported legacy mission must use modern camera action fields on export.
    archive = ZipFile(BytesIO(export_kmz(restored, timestamp_ms=1760641200001)))
    route = ET.fromstring(archive.read("wpmz/waylines.wpml"))
    first = route.findall(".//" + K + "Placemark")[0]
    for group in first.findall(W + "actionGroup"):
        params = group.find(W + "action/" + W + "actionActuatorFuncParam")
        assert params.findtext(W + "useGlobalPayloadLensIndex") == "0"


def test_mixed_legacy_and_current_xml_cannot_bypass_strict_import():
    mission = draft(drone_model="matrice4t")
    with ZipFile(BytesIO(export_kmz(mission, timestamp_ms=1760641200000))) as current:
        new_route = current.read("wpmz/waylines.wpml")
    with ZipFile(BytesIO(_previous_aeronexus_camera_kmz(mission))) as old:
        old_template = old.read("wpmz/template.kml")
    buffer = BytesIO()
    with ZipFile(buffer, "w") as output:
        output.writestr("wpmz/template.kml", old_template)
        output.writestr("wpmz/waylines.wpml", new_route)
    with pytest.raises(ValueError, match="WPML settings disagree"):
        import_kmz(buffer.getvalue())


@pytest.mark.parametrize("replacement", ["ir", "zoom", "wide,ir", ""])
def test_matrice4_lens_value_changes_rejected_on_import(replacement):
    mission = draft(drone_model="matrice4t")
    def mutate(root):
        root.find(".//" + W + "payloadLensIndex").text = replacement
    with pytest.raises(ValueError):
        import_kmz(mutated_kmz("wpmz/waylines.wpml", mutate))


def test_legacy_import_does_not_accept_arbitrary_partial_camera_fields():
    mission = draft(drone_model="matrice4t")
    with ZipFile(BytesIO(_previous_aeronexus_camera_kmz(mission))) as old:
        old_template = ET.fromstring(old.read("wpmz/template.kml"))
        old_route = old.read("wpmz/waylines.wpml")
    first_photo = old_template.find(".//" + W + "actionActuatorFuncParam")
    ET.SubElement(first_photo, W + "useGlobalPayloadLensIndex").text = "0"
    buffer = BytesIO()
    with ZipFile(buffer, "w") as output:
        output.writestr("wpmz/template.kml", ET.tostring(old_template))
        output.writestr("wpmz/waylines.wpml", old_route)
    with pytest.raises(ValueError, match="WPML settings disagree"):
        import_kmz(buffer.getvalue())
