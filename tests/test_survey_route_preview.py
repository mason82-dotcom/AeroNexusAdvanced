"""Schematic-only route sketch: deterministic, opt-in, non-executable."""
from __future__ import annotations

from math import ceil, isfinite

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from aeronexus.app import app
from aeronexus.geo_planning import GeoObject, SurveyPlanRequest, generate_survey_preview
from aeronexus.studio_page import render_studio
from aeronexus.survey_route import SurveyRouteOptions

RECTANGLE = [
    {"latitude": 49.15330, "longitude": 8.58400},
    {"latitude": 49.15330, "longitude": 8.58490},
    {"latitude": 49.15410, "longitude": 8.58490},
    {"latitude": 49.15410, "longitude": 8.58400},
]
TOKEN = "synthetic-schematic-survey-test-dashboard-token"


def polygon(vertices=RECTANGLE):
    return GeoObject(name="Synthetic rectangle", kind="polygon", vertices=vertices)


def route(**values):
    return SurveyRouteOptions(**values)


def preview(*, options=None, vertices=RECTANGLE, spacing=20, camera=None):
    return generate_survey_preview(SurveyPlanRequest(
        polygon=polygon(vertices), spacing_m=spacing,
        camera=camera, route=options,
    ))


def test_opt_in_does_not_change_existing_survey_api_shape():
    original = preview()
    explicit_none = preview(options=None)
    assert original == explicit_none
    assert "route_preview" not in original
    assert "waypoints" not in original and "flight_commands" not in original
    planned = preview(options=route())
    assert planned["legs"] == original["legs"]
    assert planned["distance_m"] == original["distance_m"]
    assert planned["kind"] == "survey-preview"


def test_route_has_one_survey_start_and_end_per_leg_and_exact_connectors():
    response = preview(options=route(speed_mps=5, turn_delay_s=7))
    sketch = response["route_preview"]
    strips = response["legs"]
    assert len(strips) == 4
    assert sketch["kind"] == "schematic-route-preview"
    assert sketch["mission_ready"] is False
    assert sketch["clearance_verified"] is False
    assert sketch["waypoint_count"] == len(sketch["points"]) == 2 * len(strips)
    assert sketch["connector_count"] == len(sketch["connectors"]) == len(strips) - 1
    for index, strip in enumerate(strips):
        start, end = sketch["points"][2*index:2*index+2]
        assert start["index"] == 2 * index + 1
        assert end["index"] == 2 * index + 2
        assert start["role"] == "strip_start" and end["role"] == "strip_end"
        assert {k: start[k] for k in ("latitude", "longitude")} == strip[0]
        assert {k: end[k] for k in ("latitude", "longitude")} == strip[1]
        if index < len(strips) - 1:
            link = sketch["connectors"][index]
            assert link["start"] == strip[1]
            assert link["end"] == strips[index+1][0]
            assert link["after_strip"] == index + 1
            assert link["clearance_verified"] is False
            assert isfinite(link["distance_m"]) and link["distance_m"] >= 0
    assert sketch["survey_distance_m"] == pytest.approx(response["distance_m"], abs=.01)
    assert sketch["total_distance_m"] == pytest.approx(
        sketch["survey_distance_m"] + sketch["connector_distance_m"], abs=.11)
    assert sketch["estimated_duration_s"] == ceil(
        (response["distance_m"] + sum(x["distance_m"] for x in sketch["connectors"])) / 5
        + sketch["connector_count"] * 7)
    assert "waypoints" not in response
    assert "flight_commands" not in response


def test_route_estimate_scales_with_speed_and_waits_without_changing_geometry():
    slow = preview(options=route(speed_mps=2, turn_delay_s=20))["route_preview"]
    fast = preview(options=route(speed_mps=10, turn_delay_s=0))["route_preview"]
    assert slow["estimated_duration_s"] > fast["estimated_duration_s"]
    assert slow["points"] == fast["points"]
    assert slow["connectors"] == fast["connectors"]
    assert slow["total_distance_m"] == fast["total_distance_m"]


def test_one_strip_has_no_connector():
    result = preview(options=route(), spacing=200)["route_preview"]
    assert result["connector_count"] == 0
    assert result["waypoint_count"] == 2
    assert result["connector_distance_m"] == 0
    assert result["estimated_duration_s"] == ceil(result["survey_distance_m"] / 5)


def test_repeatable_and_winding_independent():
    one = preview(options=route())
    assert one == preview(options=route())
    reverse = preview(options=route(), vertices=list(reversed(RECTANGLE)))
    assert reverse["route_preview"]["waypoint_count"] == one["route_preview"]["waypoint_count"]
    assert reverse["route_preview"]["total_distance_m"] == pytest.approx(
        one["route_preview"]["total_distance_m"], abs=.2)


@pytest.mark.parametrize("settings", [
    {"speed_mps": 0}, {"speed_mps": 16}, {"speed_mps": float("nan")},
    {"speed_mps": float("inf")}, {"turn_delay_s": -1},
    {"turn_delay_s": 61}, {"turn_delay_s": float("nan")},
    {"other": 12},
])
def test_invalid_options_are_rejected(settings):
    with pytest.raises(ValidationError):
        SurveyRouteOptions.model_validate(settings)


def test_authenticated_preview_is_read_only(tmp_path, monkeypatch):
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    monkeypatch.delenv("AERONEXUS_LAN_NO_TOKEN", raising=False)
    workspace = tmp_path / "workspace-must-not-be-created"
    monkeypatch.setenv("AERONEXUS_WORKSPACE_DIR", str(workspace))
    payload = {"polygon": polygon().model_dump(),
               "route": {"speed_mps": 4, "turn_delay_s": 8}}
    url = "/api/v1/studio/survey/preview"
    with TestClient(app) as client:
        assert client.post(url, json=payload).status_code in (401, 403, 503)
        ok = client.post(url, json=payload, headers={
            "Authorization": "Bearer " + TOKEN,
        })
        assert ok.status_code == 200, ok.text
        assert ok.headers["cache-control"] == "no-store"
        data = ok.json()
        assert data["route_preview"]["mission_ready"] is False
        assert data["route_preview"]["connector_count"] == data["leg_count"] - 1
        assert "flight_commands" not in data and "waypoints" not in data
        invalid = client.post(url, json={**payload,
            "route": {"speed_mps": 999}}, headers={
                "Authorization": "Bearer " + TOKEN,
            })
        assert invalid.status_code == 422
    assert not workspace.exists()


def test_studio_route_controls_are_opt_in_and_keeps_osm_default():
    page = render_studio()
    for component in (
        "survey-route-enabled", "survey-route-fields",
        "survey-route-speed", "survey-route-hold", "survey-route-metrics",
    ):
        assert f'id="{component}"' in page
    assert 'id="survey-route-enabled" type="checkbox"' in page
    assert 'function updateSurveyRouteMode()' in page
    assert 'if($("survey-route-enabled").checked)payload.route=' in page
    assert 'data.route_preview.connectors.forEach' in page
    assert 'mapTile=mapTiles.street.addTo(map);' in page
    assert 'mapTile=mapTiles.satellite.addTo(map);' not in page
    assert "No DJI" not in page or "Flugmission" in page
