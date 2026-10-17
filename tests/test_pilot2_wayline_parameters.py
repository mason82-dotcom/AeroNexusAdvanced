"""Read-only Pilot 2 WPML parameter audit regression and security tests."""
import asyncio
from io import BytesIO
import json
import sys
from zipfile import ZipFile

from aeronexus import pilot2_wayline_parameters as pm
from aeronexus.local_waylines import Credentials
from aeronexus.pilot2_wayline_preview import parse_preview_kmz
from aeronexus.wpml_export import WaypointMission, export_kmz
from aeronexus.pilot2_wayline_compare import compare_geometry


WORKSPACE = "12345678-1234-4234-8234-123456789012"
WAYLINE = "00000000-0000-0000-0000-000000000011"
CREDS = Credentials(WORKSPACE, "test-secret-token-123456789")


def mission(**kwargs):
    data = {"name": "Private survey", "drone_model": "matrice4t",
            "speed_mps": 5.0, "altitude_m": 50.0,
            "waypoints": [
                {"latitude": 49.12, "longitude": 8.5, "take_photo": True},
                {"latitude": 49.13, "longitude": 8.6},
            ]}
    data.update(kwargs)
    return WaypointMission.model_validate(data)


def raw_kmz(m=None):
    return export_kmz(m or mission(), timestamp_ms=1730000000000)


def modified_kmz(old, new, kmz=None):
    result = BytesIO()
    with ZipFile(BytesIO(kmz or raw_kmz())) as original, ZipFile(result, "w") as target:
        for name in original.namelist():
            data = original.read(name)
            if name.endswith("waylines.wpml"):
                assert old in data
                data = data.replace(old, new)
            target.writestr(name, data)
    return result.getvalue()


def report(mission_obj, data, meta="0-99-1"):
    cloud = {"device_model_key": meta}
    geometry = compare_geometry(mission_obj, cloud, parse_preview_kmz(data))
    return pm.compare_parameters(mission_obj, pm.parse_parameter_audit(data), geometry, meta)


def test_generated_wpml_fields_match_but_never_complete_content():
    r = report(mission(), raw_kmz())
    assert r["route_count"] == 1
    assert r["route_point_counts"] == [2]
    assert r["height_modes"] == ["relativeToStartPoint"]
    assert r["wpml_model_key"] == "0-99-1"
    assert r["cloud_metadata_wpml_agree"] is True
    assert r["photo_action_count"] == 1
    assert r["other_action_count"] == 0
    assert r["geometry_result"] == "coordinates_equal"
    assert r["parameter_state"] == "supported_fields_equal"
    assert r["parameter_matches"]["waypointHeights"] is True
    assert r["parameter_matches"]["takePhotoPositions"] is True
    assert r["full_content_verified"] is False
    assert r["flight_compatibility_verified"] is False
    encoded = json.dumps(r)
    assert not any(x in encoded for x in ("49.12", "8.5,", "Private survey", WAYLINE, CREDS.access_token))


def test_undocumented_altitude_frame_is_never_compared_numerically():
    kmz = modified_kmz(b"<wpml:executeHeightMode>relativeToStartPoint</wpml:executeHeightMode>",
                       b"<wpml:executeHeightMode>WGS84</wpml:executeHeightMode>")
    r = report(mission(), kmz)
    assert r["parameter_matches"]["executeHeightMode"] is False
    assert r["parameter_matches"]["waypointHeights"] is None
    assert r["parameter_state"] == "differences_detected"


def test_parameter_differences_visible_only_after_exact_single_route_match():
    kmz = modified_kmz(b"<wpml:waypointSpeed>5</wpml:waypointSpeed>",
                       b"<wpml:waypointSpeed>8</wpml:waypointSpeed>")
    r = report(mission(), kmz)
    assert r["geometry_result"] == "coordinates_equal"
    assert r["parameter_matches"]["waypointSpeeds"] is False
    assert r["parameter_state"] == "differences_detected"
    other = report(mission(waypoints=[
        {"latitude": 49.14, "longitude": 8.5},
        {"latitude": 49.13, "longitude": 8.6},
    ]), kmz)
    assert other["geometry_result"] == "coordinates_different"
    assert other["parameter_state"] == "not_comparable"
    assert other["parameter_matches"] == {}


def test_model_metadata_and_embedded_wpml_can_disagree():
    r = report(mission(), raw_kmz(), meta="0-77-2")
    assert r["cloud_metadata_wpml_agree"] is False
    assert r["wpml_model_match"] is True
    assert r["geometry_result"] == "model_conflict"
    assert r["parameter_state"] == "not_comparable"


def test_embedded_drone_model_conflict_blocks_parameter_equal_claim():
    kmz = modified_kmz(b"<wpml:droneEnumValue>99</wpml:droneEnumValue>",
                       b"<wpml:droneEnumValue>77</wpml:droneEnumValue>")
    r = report(mission(), kmz)
    assert r["geometry_result"] == "coordinates_equal"
    assert r["wpml_model_match"] is False
    assert r["cloud_metadata_wpml_agree"] is False
    assert r["parameter_state"] == "not_comparable"
    assert r["parameter_matches"] == {}


def test_unknown_actions_never_report_camera_match():
    kmz = modified_kmz(b"<wpml:actionActuatorFunc>takePhoto</wpml:actionActuatorFunc>",
                       b"<wpml:actionActuatorFunc>rotateYaw</wpml:actionActuatorFunc>")
    r = report(mission(), kmz)
    assert r["other_action_count"] == 1
    assert r["parameter_matches"]["takePhotoPositions"] is None
    assert r["full_content_verified"] is False


def test_missing_fields_always_remain_incomplete():
    kmz = modified_kmz(b"<wpml:globalRTHHeight>60</wpml:globalRTHHeight>", b"")
    r = report(mission(), kmz)
    assert r["parameter_matches"]["globalRTHHeight"] is None
    assert r["parameter_state"] == "incomplete_fields"


def test_corrupt_xml_or_missing_wpml_archive_fail_closed():
    from aeronexus.local_waylines import LocalWaylineError
    import pytest
    with pytest.raises(LocalWaylineError, match="invalid_archive"):
        pm.parse_parameter_audit(b"invalid")
    with pytest.raises(LocalWaylineError, match="invalid_archive"):
        pm.parse_parameter_audit(
            modified_kmz(b"<wpml:waypointSpeed>", b"<!DOCTYPE kml><wpml:waypointSpeed>"))


def test_opt_in_reader_requires_complete_inventory_and_never_returns_ids():
    seen = []
    async def inventory(_):
        return {"state": "connected", "workspace_id": WORKSPACE,
                "pagination_complete": True, "reported_total": 1,
                "waylines": [{"wayline_id": WAYLINE, "device_model_key": "0-99-1"}]}
    async def downloader(_, ident):
        seen.append(ident)
        return raw_kmz()
    loader = lambda _: CREDS
    out = asyncio.run(pm.diagnose_parameters(
        mission(), inventory_reader=inventory, kmz_reader=downloader,
        credentials_loader=loader))
    assert out["inventory_state"] == "connected"
    assert out["results"][0]["parameter_state"] == "supported_fields_equal"
    assert seen == [WAYLINE]
    assert WAYLINE not in json.dumps(out)
    seen.clear()
    async def partial(_):
        return {**(await inventory(_)), "pagination_complete": False}
    refused = asyncio.run(pm.diagnose_parameters(
        mission(), inventory_reader=partial, kmz_reader=downloader,
        credentials_loader=loader))
    assert refused["inventory_state"] == "incomplete_inventory" and seen == []


def test_command_outputs_no_ids_coords_or_names(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["audit", "--mission", WORKSPACE])
    monkeypatch.setattr(pm, "read_local_mission", lambda _: mission())
    async def fake(_mission, *, limit):
        assert limit == 8
        return {"inventory_state": "connected", "results": [
            {"index": 1, "state": "connected", "parameter_state": "not_comparable"}]}
    monkeypatch.setattr(pm, "diagnose_parameters", fake)
    assert pm.main() == 0
    text = capsys.readouterr().out
    assert WORKSPACE not in text
    assert "Private survey" not in text
    assert CREDS.access_token not in text
