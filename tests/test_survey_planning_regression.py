"""Regression contracts for local, preview-only Leaflet survey planning.

These checks use synthetic geometries and never contact a drone, DJI Cloud
API, mapping service, or local production workspace.
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from aeronexus.app import app
from aeronexus.geo_planning import GeoObject, SurveyPlanRequest, generate_survey_preview


RECTANGLE = [
    {"latitude": 49.15330, "longitude": 8.58400},
    {"latitude": 49.15330, "longitude": 8.58490},
    {"latitude": 49.15410, "longitude": 8.58490},
    {"latitude": 49.15410, "longitude": 8.58400},
]
TOKEN = "aeronexus-survey-regression-test-token-not-a-dji-token"


def area(vertices=None):
    return GeoObject(name="Synthetic survey", kind="polygon", vertices=vertices or RECTANGLE)


def preview(vertices=None, *, spacing=20, bearing=0):
    return generate_survey_preview(SurveyPlanRequest(
        polygon=area(vertices), spacing_m=spacing, bearing_deg=bearing,
    ))


def test_known_rectangle_has_four_clipped_legs_and_no_executable_route():
    result = preview()
    assert result["kind"] == "survey-preview"
    assert result["leg_count"] == len(result["legs"]) == 4
    assert result["distance_m"] == pytest.approx(355.6, abs=0.2)
    assert "waypoints" not in result
    assert "no safe connecting turns" in result["note"]
    for leg in result["legs"]:
        assert len(leg) == 2
        for point in leg:
            assert RECTANGLE[0]["latitude"] - 1e-6 <= point["latitude"] <= RECTANGLE[2]["latitude"] + 1e-6
            assert RECTANGLE[0]["longitude"] - 1e-6 <= point["longitude"] <= RECTANGLE[1]["longitude"] + 1e-6


def test_preview_is_deterministic_and_polygon_winding_is_irrelevant():
    first = preview()
    assert preview() == first
    reverse = preview(list(reversed(RECTANGLE)))
    assert reverse["leg_count"] == first["leg_count"]
    assert reverse["distance_m"] == pytest.approx(first["distance_m"], abs=0.1)


def test_wider_lane_spacing_reduces_required_legs():
    narrow = preview(spacing=20)
    wide = preview(spacing=40)
    assert wide["leg_count"] < narrow["leg_count"]
    assert wide["distance_m"] < narrow["distance_m"]


def test_bearing_changes_lane_direction_and_count():
    north_south = preview(bearing=0)
    east_west = preview(bearing=90)
    assert east_west["leg_count"] != north_south["leg_count"]


def test_self_intersecting_or_degenerate_polygon_is_rejected():
    bow_tie = [RECTANGLE[0], RECTANGLE[2], RECTANGLE[1], RECTANGLE[3]]
    with pytest.raises(ValidationError):
        area(bow_tie)
    with pytest.raises(ValidationError):
        area([RECTANGLE[0], RECTANGLE[1], RECTANGLE[1], RECTANGLE[3]])


def test_dateline_and_invalid_spacing_are_rejected():
    crossing = [
        {"latitude": 49.0, "longitude": 179.9},
        {"latitude": 49.0, "longitude": -179.9},
        {"latitude": 49.1, "longitude": -179.9},
        {"latitude": 49.1, "longitude": 179.9},
    ]
    with pytest.raises(ValidationError):
        area(crossing)
    for bad in (1, 201):
        with pytest.raises(ValidationError):
            SurveyPlanRequest(polygon=area(), spacing_m=bad)


def test_excessive_number_of_lanes_is_rejected():
    oversized = [
        {"latitude": 49.0, "longitude": 8.0},
        {"latitude": 49.0, "longitude": 8.1},
        {"latitude": 49.1, "longitude": 8.1},
        {"latitude": 49.1, "longitude": 8.0},
    ]
    with pytest.raises(ValueError, match="Too many flight lines"):
        preview(oversized, spacing=2)


def test_api_requires_access_and_keeps_workspace_unmodified(tmp_path, monkeypatch):
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    workspace = tmp_path / "untouched-workspace"
    monkeypatch.setenv("AERONEXUS_WORKSPACE_DIR", str(workspace))
    payload = {
        "polygon": area().model_dump(),
        "spacing_m": 20,
        "bearing_deg": 0,
    }
    with TestClient(app) as client:
        path = "/api/v1/studio/survey/preview"
        unauthorized = client.post(path, json=payload)
        assert unauthorized.status_code in (401, 403, 503)
        authorized = client.post(path, json=payload, headers={"Authorization": f"Bearer {TOKEN}"})
        assert authorized.status_code == 200, authorized.text
        assert authorized.json()["leg_count"] == 4
        assert authorized.json()["kind"] == "survey-preview"
        assert authorized.headers["cache-control"] == "no-store"
        assert not workspace.exists()
        invalid = client.post(path, json={**payload, "spacing_m": 1},
                              headers={"Authorization": f"Bearer {TOKEN}"})
        assert invalid.status_code == 422
