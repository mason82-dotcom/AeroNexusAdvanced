"""Opt-in 2D fillet analysis, conservative polygon diagnostics, no flight safety."""
from __future__ import annotations

from math import cos, isfinite, radians
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from aeronexus.app import app
from aeronexus.geo_planning import GeoObject, SurveyPlanRequest, generate_survey_preview
from aeronexus.studio_page import render_studio
from aeronexus.survey_camera import SurveyCameraRequest
from aeronexus.survey_route import SurveyRouteOptions
from aeronexus.survey_turns import build_turn_geometry

RECTANGLE = [
    {"latitude": 49.15330, "longitude": 8.58400},
    {"latitude": 49.15330, "longitude": 8.58490},
    {"latitude": 49.15410, "longitude": 8.58490},
    {"latitude": 49.15410, "longitude": 8.58400},
]
TOKEN = "synthetic-2d-turn-test-dashboard-token-32"


def polygon(vertices=RECTANGLE):
    return GeoObject(name="Synthetic rectangle", kind="polygon", vertices=vertices)


def plan(*, radius=None, camera=None, speed=5):
    return generate_survey_preview(SurveyPlanRequest(
        polygon=polygon(), spacing_m=20, bearing_deg=0,
        camera=camera,
        route=SurveyRouteOptions(speed_mps=speed, turn_delay_s=5, turn_radius_m=radius),
    ))


def test_opt_in_must_not_change_existing_legacy_preview():
    old = generate_survey_preview(SurveyPlanRequest(polygon=polygon()))
    no_radius = plan()
    with_radius = plan(radius=5)
    assert "route_preview" not in old
    assert "turn_geometry" not in no_radius["route_preview"]
    for key in ("kind", "legs", "leg_count", "distance_m", "note"):
        assert old[key] == no_radius[key] == with_radius[key]
    base = no_radius["route_preview"].copy()
    new = with_radius["route_preview"].copy()
    del new["turn_geometry"]
    assert base == new
    assert "waypoints" not in with_radius and "flight_commands" not in with_radius


def test_five_metre_arcs_round_each_connector_of_rectangle():
    r = plan(radius=5)
    sketch = r["route_preview"]
    turns = sketch["turn_geometry"]
    assert r["leg_count"] == 4
    assert turns["kind"] == "geometric-turn-analysis"
    assert turns["radius_m"] == 5
    assert turns["geometry_available_count"] == 3
    assert turns["geometry_rejected_count"] == 0
    assert turns["geometry_complete"] is True
    assert turns["polygon_exit_count"] == 0
    assert turns["curve_total_distance_m"] < sketch["total_distance_m"]
    assert turns["estimated_duration_s"] > 0
    for i, turn in enumerate(turns["connections"]):
        assert turn["after_strip"] == i + 1
        assert turn["geometry_available"] is True
        assert turn["polygon_exit_detected"] is False
        assert 75 < turn["entry_turn_deg"] < 105
        assert 75 < turn["exit_turn_deg"] < 105
        assert turn["curve_distance_m"] > 0
        assert len(turn["curve_points"]) >= 4
        assert all(isfinite(v) for p in turn["curve_points"] for v in p.values())


def test_unreachable_radius_rejects_geometry_instead_of_claiming_safety():
    r = plan(radius=30)["route_preview"]["turn_geometry"]
    assert r["geometry_complete"] is False
    assert r["geometry_rejected_count"] > 0
    assert r["curve_total_distance_m"] is None
    assert r["estimated_duration_s"] is None
    assert all((not c["geometry_available"] and c["curve_points"] == [])
               or c["geometry_available"] for c in r["connections"])
    assert r["ready_for_flight"] is False
    assert r["terrain_verified"] is False
    assert r["obstacles_verified"] is False
    assert r["battery_verified"] is False
    assert r["rth_verified"] is False


def test_single_leg_has_no_rounding_and_no_false_clearance():
    r = generate_survey_preview(SurveyPlanRequest(
        polygon=polygon(), spacing_m=200, route=SurveyRouteOptions(turn_radius_m=5)))
    t = r["route_preview"]["turn_geometry"]
    assert r["leg_count"] == 1
    assert t["connections"] == []
    assert t["geometry_complete"] is True
    assert t["curve_total_distance_m"] == pytest.approx(r["distance_m"], abs=.1)
    assert t["ready_for_flight"] is False


def test_polygon_concavity_detects_schematic_connection_leaving_boundary():
    # A concave U region with a notch open toward y=5; both strips remain
    # inside the left/right arms but the connector cuts through the notch.
    lat0, lon0 = 49., 8.
    sx = 111320 * cos(radians(lat0))
    def gps(x, y):
        return {"latitude": lat0 + 20 * y / 111132,
                "longitude": lon0 + 20 * x / sx}
    poly = [gps(x,y) for x,y in [
        (0,0),(5,0),(5,5),(3,5),(3,2),(2,2),(2,5),(0,5)]]
    legs = [[gps(1,3),gps(1,4)], [gps(4,4),gps(4,3)]]
    t = build_turn_geometry(legs, poly, 40, 5, 5, 5)
    assert t["geometry_complete"] is True
    assert t["polygon_exit_count"] == 1
    assert t["connections"][0]["polygon_exit_detected"] is True
    assert t["ready_for_flight"] is False


def test_turn_geometry_is_deterministic_and_with_camera_unchanged():
    camera = SurveyCameraRequest(profile_id="matrice-4e-wide")
    before = plan(camera=camera)
    rounded = plan(radius=5, camera=camera)
    assert rounded == plan(radius=5, camera=camera)
    assert rounded["camera_plan"] == before["camera_plan"]
    assert rounded["legs"] == before["legs"]


def test_speed_changes_only_estimated_turn_time():
    slow = plan(radius=5, speed=2)["route_preview"]["turn_geometry"]
    fast = plan(radius=5, speed=10)["route_preview"]["turn_geometry"]
    assert slow["connections"] == fast["connections"]
    assert slow["estimated_duration_s"] > fast["estimated_duration_s"]


@pytest.mark.parametrize("radius", [0, 1, 31, float("nan"), float("inf"), -2])
def test_bad_turn_radius_rejected_by_pydantic(radius):
    with pytest.raises(ValidationError):
        SurveyRouteOptions(turn_radius_m=radius)


def test_api_requires_access_and_never_writes_missions(tmp_path, monkeypatch):
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    monkeypatch.delenv("AERONEXUS_LAN_NO_TOKEN", raising=False)
    workspace = tmp_path / "must-stay-absent"
    monkeypatch.setenv("AERONEXUS_WORKSPACE_DIR", str(workspace))
    payload = {"polygon": polygon().model_dump(),
               "route": {"speed_mps": 5, "turn_delay_s": 5, "turn_radius_m": 5}}
    path = "/api/v1/studio/survey/preview"
    with TestClient(app) as client:
        assert client.post(path, json=payload).status_code in (401,403,503)
        response = client.post(path, json=payload, headers={
            "Authorization": "Bearer " + TOKEN})
        assert response.status_code == 200, response.text
        body = response.json()
        turns = body["route_preview"]["turn_geometry"]
        assert turns["ready_for_flight"] is False
        assert turns["terrain_verified"] is False
        assert turns["geometry_available_count"] == 3
        assert "flight_commands" not in body and "waypoints" not in body
        assert response.headers["cache-control"] == "no-store"
        for bad in (0,31):
            wrong = {"polygon":payload["polygon"], "route":{
                **payload["route"], "turn_radius_m":bad}}
            assert client.post(path,json=wrong,headers={
                "Authorization":"Bearer "+TOKEN}).status_code==422
    assert not workspace.exists()


def test_studio_is_opt_in_and_has_unverified_geometry_warning():
    html = render_studio()
    for name in ("survey-turn-enabled","survey-turn-options",
                 "survey-turn-radius","survey-turn-metrics"):
        assert f'id="{name}"' in html
    assert 'id="survey-turn-enabled" type="checkbox" disabled' in html
    assert 'payload.route.turn_radius_m=Number($("survey-turn-radius").value)' in html
    assert 'turns.geometry_complete' in html
    assert 'data.route_preview.turn_geometry?.connections' in html
    assert 'mapTile=mapTiles.street.addTo(map);' in html
    assert 'mapTile=mapTiles.satellite.addTo(map);' not in html
    assert 'Keine Kollisions-' in html
