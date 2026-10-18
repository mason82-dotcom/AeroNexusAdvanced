"""DJI optical survey-preview contracts; uses no drone or persisted mission state."""
import math

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from aeronexus.app import app
from aeronexus.geo_planning import GeoObject, SurveyPlanRequest, generate_survey_preview
from aeronexus.studio_page import render_studio
from aeronexus.survey_camera import CAMERA_PROFILES, SurveyCameraRequest, camera_footprint


RECTANGLE = [
    {"latitude": 49.15330, "longitude": 8.58400},
    {"latitude": 49.15330, "longitude": 8.58490},
    {"latitude": 49.15410, "longitude": 8.58490},
    {"latitude": 49.15410, "longitude": 8.58400},
]
TOKEN = "survey-camera-test-dashboard-token-32chars-not-dji"


def polygon():
    return GeoObject(name="Synthetic camera area", kind="polygon", vertices=RECTANGLE)


def config(profile_id="matrice-4e-wide", **kwargs):
    return SurveyCameraRequest(profile_id=profile_id, **kwargs)


def test_profile_catalog_covers_requested_dji_optics_and_vendor_sources():
    assert len(CAMERA_PROFILES) == 6
    for profile_id, profile in CAMERA_PROFILES.items():
        assert profile["source"].startswith("https://")
        assert "dji.com/" in profile["source"]
        assert profile["image_width_px"] >= 2500
        assert profile["image_height_px"] >= 1800
        assert 70 < profile["diagonal_fov_deg"] < 90
        assert camera_footprint(config(profile_id))["profile_id"] == profile_id


def test_gsd_and_optics_are_consistent_with_diagonal_fov():
    settings = config(height_agl_m=60, side_overlap_pct=70, front_overlap_pct=80)
    result = camera_footprint(settings)
    profile = CAMERA_PROFILES[settings.profile_id]
    aspect = profile["image_width_px"] / profile["image_height_px"]
    assert result["footprint_width_m"] / result["footprint_length_m"] == pytest.approx(
        aspect, rel=0.001)
    expected_diagonal = 120 * math.tan(math.radians(84) / 2)
    assert math.hypot(result["footprint_width_m"], result["footprint_length_m"]) == pytest.approx(
        expected_diagonal, rel=0.001)
    assert result["gsd_cm_px"] == pytest.approx(
        result["footprint_width_m"] / 5280 * 100, abs=0.003)
    assert result["spacing_m"] == pytest.approx(
        result["footprint_width_m"] * 0.30, abs=0.01)
    assert result["trigger_interval_m"] == pytest.approx(
        result["footprint_length_m"] * 0.2, abs=0.01)


def test_height_double_scales_footprint_and_gsd():
    a, b = (camera_footprint(config(height_agl_m=x))
            for x in (50, 100))
    for key in ("footprint_width_m", "footprint_length_m",
                "gsd_cm_px", "spacing_m", "trigger_interval_m"):
        assert b[key] == pytest.approx(a[key] * 2, abs=0.01)


def test_mavic3m_multispectral_mode_has_distinct_gsd():
    rgb = camera_footprint(config("mavic-3m-rgb"))
    ms = camera_footprint(config("mavic-3m-ms"))
    assert rgb["gsd_cm_px"] != ms["gsd_cm_px"]
    assert ms["gsd_cm_px"] > rgb["gsd_cm_px"]
    assert "G/R/RE/NIR" in ms["capture_mode"]


def test_automatic_overlap_increases_flight_strip_count():
    loose = generate_survey_preview(SurveyPlanRequest(
        polygon=polygon(), camera=config(side_overlap_pct=50)))
    dense = generate_survey_preview(SurveyPlanRequest(
        polygon=polygon(), camera=config(side_overlap_pct=80)))
    assert dense["leg_count"] > loose["leg_count"]
    assert dense["camera_plan"]["spacing_m"] < loose["camera_plan"]["spacing_m"]
    assert dense["camera_plan"]["estimated_photo_count"] > loose["camera_plan"]["estimated_photo_count"]
    assert all(len(leg) == 2 for leg in dense["legs"])
    assert "waypoints" not in dense and "flight_commands" not in dense


def test_front_overlap_changes_photo_estimate_not_route():
    first = generate_survey_preview(SurveyPlanRequest(
        polygon=polygon(), camera=config(front_overlap_pct=60)))
    second = generate_survey_preview(SurveyPlanRequest(
        polygon=polygon(), camera=config(front_overlap_pct=85)))
    assert first["legs"] == second["legs"]
    assert first["camera_plan"]["estimated_photo_count"] < second["camera_plan"]["estimated_photo_count"]


def test_manual_mode_remains_backward_compatible():
    old = generate_survey_preview(SurveyPlanRequest(polygon=polygon(), spacing_m=20))
    explicit = generate_survey_preview(SurveyPlanRequest(
        polygon=polygon(), spacing_m=20, camera=None))
    assert old == explicit
    assert old["leg_count"] == 4
    assert "camera_plan" not in old


@pytest.mark.parametrize("settings", [
    {"height_agl_m": 0},
    {"height_agl_m": 301},
    {"side_overlap_pct": 100},
    {"side_overlap_pct": 20},
    {"front_overlap_pct": 99},
    {"front_overlap_pct": -2},
    {"profile_id": "invalid-profile"},
    {"height_agl_m": float("nan")},
    {"side_overlap_pct": float("inf")},
    {"bad_field": 123},
])
def test_invalid_camera_inputs_fail_closed(settings):
    params = {"profile_id": "matrice-4e-wide", **settings}
    with pytest.raises(ValidationError):
        SurveyCameraRequest.model_validate(params)


def test_spacing_guard_applies_to_camera_derived_value():
    with pytest.raises(ValueError, match="Camera-derived spacing"):
        generate_survey_preview(SurveyPlanRequest(
            polygon=polygon(), camera=config(height_agl_m=10, side_overlap_pct=90)))
    with pytest.raises(ValueError, match="Camera-derived spacing"):
        generate_survey_preview(SurveyPlanRequest(
            polygon=polygon(), camera=config(height_agl_m=300, side_overlap_pct=40)))


def test_authenticated_api_preview_uses_no_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    monkeypatch.delenv("AERONEXUS_LAN_NO_TOKEN", raising=False)
    workspace = tmp_path / "should-not-be-created"
    monkeypatch.setenv("AERONEXUS_WORKSPACE_DIR", str(workspace))
    payload = {
        "polygon": polygon().model_dump(), "spacing_m": 20, "bearing_deg": 0,
        "camera": config().model_dump()
    }
    with TestClient(app) as client:
        endpoint = "/api/v1/studio/survey/preview"
        unauthorized = client.post(endpoint, json=payload)
        assert unauthorized.status_code in (401, 403, 503)
        response = client.post(endpoint, json=payload, headers={
            "Authorization": f"Bearer {TOKEN}"})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["camera_plan"]["estimated_photo_count"] > 0
        assert result["camera_plan"]["spacing_m"] > 2
        assert result["kind"] == "survey-preview"
        assert "waypoints" not in result
        assert response.headers["cache-control"] == "no-store"
        assert not workspace.exists()
        invalid = client.post(endpoint, json={
            **payload, "camera": {**payload["camera"], "profile_id": "fake"}
        }, headers={"Authorization": f"Bearer {TOKEN}"})
        assert invalid.status_code == 422


def test_studio_has_camera_ui_and_keeps_manual_default():
    page = render_studio()
    for element_id in (
        "survey-camera", "survey-camera-fields", "survey-height-agl",
        "survey-side-overlap", "survey-front-overlap", "survey-camera-metrics",
        "survey-spacing", "survey-generate"
    ):
        assert f'id="{element_id}"' in page
    for profile_id in CAMERA_PROFILES:
        assert f'value="{profile_id}"' in page
    assert '<option value="">Manuell · Spurabstand eingeben</option>' in page
    assert 'function updateSurveyCameraMode()' in page
    assert 'function surveyPreview()' in page
    assert 'payload.camera={' in page
    assert "innerHTML" not in page
    assert "/api/v1/flight/command" not in page
