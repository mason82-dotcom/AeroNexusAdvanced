"""Pilot 2 geometry-only comparison: no writes and no false content equality."""
import asyncio
import json
import sys
from uuid import UUID

import pytest

from aeronexus import pilot2_wayline_compare as cmp
from aeronexus.local_waylines import Credentials
from aeronexus.studio_workspace import Workspace
from aeronexus.wpml_export import WaypointMission


MID = "12345678-1234-4234-8234-123456789012"
WID = str(UUID(int=17))
CREDS = Credentials(MID, "geometry-only-secret-token-123456789")


def mission(**changes):
    return WaypointMission.model_validate({
        "name": "Private inspection",
        "drone_model": "matrice4t",
        "waypoints": [
            {"latitude": 49.12, "longitude": 8.5},
            {"latitude": 49.13, "longitude": 8.6},
        ],
        **changes,
    })


def preview(*segments):
    return {"source": "waylines.wpml", "features": [
        {"geometry": {"type": "LineString", "coordinates": pts}}
        for pts in segments
    ]}


def test_exact_coordinate_match_is_not_full_content_verification():
    result = cmp.compare_geometry(mission(), {"device_model_key": "0-99-1"},
                                  preview([[8.5, 49.12], [8.6, 49.13]]))
    assert result["geometry_result"] == "coordinates_equal"
    assert result["model_match"] is True
    assert result["full_content_verified"] is False
    assert result["flight_compatibility_verified"] is False
    assert "Private inspection" not in json.dumps(result)


def test_multiple_wayline_segments_never_claim_exact_match():
    planned = [[8.5, 49.12], [8.6, 49.13]]
    extra = [[8.7, 49.11], [8.8, 49.11]]
    first = cmp.compare_geometry(mission(), {"device_model_key": "0-99-1"},
                                 preview(planned, extra))
    assert first["geometry_result"] == "matching_segment_with_extras"
    assert first["cloud_feature_count"] == 2
    split = cmp.compare_geometry(mission(), {},
                                 preview(planned[:1], planned[1:]))
    assert split["geometry_result"] == "multipart_order_matches"
    assert split["model_match"] is None


def test_mismatch_model_conflict_and_unusable_template():
    wrong = cmp.compare_geometry(mission(), {}, preview([[8.5, 49.12], [8.7, 49.13]]))
    assert wrong["geometry_result"] == "coordinates_different"
    conflict = cmp.compare_geometry(mission(), {"device_model_key": "0-77-0"},
                                    preview([[8.5, 49.12], [8.6, 49.13]]))
    assert conflict["geometry_result"] == "model_conflict"
    template = cmp.compare_geometry(mission(), {},
                                    {"source": "template.kml", "features": [
                                        {"geometry": {"type": "Polygon", "coordinates": []}}]})
    assert template["geometry_result"] == "unsupported_geometry"


def test_closed_route_compared_as_actually_exported_waypoints():
    closed = WaypointMission.model_validate({
        "name": "Triangle", "close_route": True,
        "waypoints": [
            {"latitude": 49.1, "longitude": 8.5},
            {"latitude": 49.2, "longitude": 8.6},
            {"latitude": 49.3, "longitude": 8.7},
        ],
    })
    result = cmp.compare_geometry(closed, {}, preview([
        [8.5, 49.1], [8.6, 49.2], [8.7, 49.3], [8.5, 49.1]]))
    assert result["geometry_result"] == "coordinates_equal"
    assert result["studio_point_count"] == 4


def test_malformed_or_unapproved_geometry_never_matches():
    for coords in ([[8.5, 49.12, 10], [8.6, 49.13]],
                   [[float("nan"), 49.12], [8.6, 49.13]],
                   [[8.5, 49.12], [181, 49.13]],
                   [[8.5, 49.12], ["secret", 49.13]]):
        result = cmp.compare_geometry(mission(), {}, preview(coords))
        assert result["geometry_result"] == "unsupported_geometry"


def test_inventory_must_be_complete_and_id_must_match_before_download():
    seen = []
    async def read_inventory(credentials):
        assert credentials == CREDS
        return {"state": "connected", "workspace_id": MID,
                "pagination_complete": True,
                "waylines": [{"wayline_id": WID, "device_model_key": "0-99-1"}]}
    async def read_preview(credentials, route_id):
        seen.append(route_id)
        return preview([[8.5, 49.12], [8.6, 49.13]])
    def load(_):
        return CREDS
    good = asyncio.run(cmp.check_mission(
        mission(), WID, inventory_reader=read_inventory,
        preview_reader=read_preview, load=load))
    assert good["geometry_result"] == "coordinates_equal"
    assert seen == [WID]
    seen.clear()
    async def incomplete(credentials):
        out = await read_inventory(credentials)
        return {**out, "pagination_complete": False}
    blocked = asyncio.run(cmp.check_mission(
        mission(), WID, inventory_reader=incomplete,
        preview_reader=read_preview, load=load))
    assert blocked == {"state": "incomplete_inventory"} and seen == []
    absent = asyncio.run(cmp.check_mission(
        mission(), str(UUID(int=21)), inventory_reader=read_inventory,
        preview_reader=read_preview, load=load))
    assert absent == {"state": "wayline_not_found"} and seen == []
    no_creds = asyncio.run(cmp.check_mission(mission(), WID, load=lambda _: None))
    assert no_creds == {"state": "not_configured"}


def test_workspace_reads_without_creating_or_mutating(tmp_path, monkeypatch):
    empty = tmp_path / "absent"
    monkeypatch.setenv("AERONEXUS_WORKSPACE_DIR", str(empty))
    with pytest.raises(Exception):
        cmp.read_local_mission(MID)
    assert not empty.exists()
    ws = Workspace(tmp_path / "private")
    saved = ws.save_mission(mission())
    before = {p: p.read_bytes() for p in ws.root.rglob("*.json")}
    monkeypatch.setenv("AERONEXUS_WORKSPACE_DIR", str(ws.root))
    loaded = cmp.read_local_mission(saved["id"])
    assert loaded.name == "Private inspection"
    assert before == {p: p.read_bytes() for p in ws.root.rglob("*.json")}


def test_cli_output_omits_ids_names_coordinates_and_secrets(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["compare", "--mission", MID, "--wayline", WID])
    monkeypatch.setattr(cmp, "read_local_mission", lambda _: mission())
    async def check(_, __):
        return {"state": "connected", "geometry_result": "coordinates_equal",
                "full_content_verified": False}
    monkeypatch.setattr(cmp, "check_mission", check)
    assert cmp.main() == 0
    output = capsys.readouterr().out
    assert all(v not in output for v in (MID, WID, "8.5", "49.12",
                                         "Private inspection", CREDS.access_token))
    assert json.loads(output)["full_content_verified"] is False
