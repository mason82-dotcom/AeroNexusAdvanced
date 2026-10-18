"""Contracts for Pi-only, CA-verified live survey smoke (all CI tests offline)."""
import importlib.util
import json
from pathlib import Path

import pytest

from aeronexus.geo_planning import GeoObject, SurveyPlanRequest, generate_survey_preview


SOURCE = Path(__file__).resolve().parents[1] / "scripts/pi/studio_live_survey_smoke.py"
SPEC = importlib.util.spec_from_file_location("studio_live_survey", SOURCE)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


def sample_record():
    return {
        "id": "00000000-0000-4000-8000-000000000001",
        "object": {"name": "Synthetic", "kind": "polygon",
                   "vertices": smoke.RECTANGLE, "radius_m": None},
        "updated_at": "2026-10-18T19:00:00Z",
    }


def test_request_allowlist_covers_no_state_mutations():
    assert smoke.ALLOWED_HTTP == {
        ("GET", "/health"),
        ("GET", "/studio"),
        ("GET", "/api/v1/studio/geo-objects"),
        ("POST", "/api/v1/studio/survey/preview"),
    }
    assert not any("mission" in path or "flight" in path
                   for method, path in smoke.ALLOWED_HTTP)


def test_saved_polygon_selection_ignores_nonpolygons():
    selected, total = smoke.choose_polygon([
        {"id": "point", "object": {"kind": "point"}},
        sample_record()
    ], 0)
    assert selected["id"] == sample_record()["id"]
    assert total == 1
    with pytest.raises(smoke.LiveSmokeError):
        smoke.choose_polygon([], 0)
    with pytest.raises(smoke.LiveSmokeError):
        smoke.choose_polygon([sample_record()], 1)


def test_validated_preview_remains_nonexecuting():
    record = sample_record()
    polygon = GeoObject.model_validate(record["object"])
    result = generate_survey_preview(SurveyPlanRequest(
        polygon=polygon, spacing_m=20, bearing_deg=0))
    count, length = smoke.validate_preview(result, record["object"])
    assert count == 4
    assert length == pytest.approx(355.6, abs=0.2)
    assert "waypoints" not in result


@pytest.mark.parametrize("mutate", [
    lambda r: {**r, "kind": "waypoint"},
    lambda r: {**r, "leg_count": 100},
    lambda r: {**r, "distance_m": float("nan")},
    lambda r: {**r, "waypoints": []},
    lambda r: {**r, "legs": [
        [{"latitude": -80, "longitude": 0},
         {"latitude": -80, "longitude": 0}]
    ] + r["legs"][1:]},
])
def test_rejects_invalid_preview_payloads(mutate):
    record = sample_record()
    polygon = GeoObject.model_validate(record["object"])
    valid = generate_survey_preview(SurveyPlanRequest(
        polygon=polygon, spacing_m=20, bearing_deg=0))
    with pytest.raises(smoke.LiveSmokeError):
        smoke.validate_preview(mutate(valid), record["object"])


def test_api_request_rejects_unallowlisted_write_without_io():
    class ShouldNotConnect:
        def open(self, *args, **kwargs):
            raise AssertionError("Disallowed request reached IO")
    with pytest.raises(smoke.LiveSmokeError, match="Non-allowlisted"):
        smoke.call_api(ShouldNotConnect(), "DELETE", "/api/v1/studio/geo-objects")


def test_api_get_and_preview_methods_only(monkeypatch):
    monkeypatch.delenv("AERONEXUS_STATUS_TOKEN", raising=False)
    events = []

    class FakeResponse:
        status = 200
        def __init__(self, body):
            self.body = body
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, length):
            return self.body

    class Opener:
        def open(self, req, timeout):
            events.append((req.get_method(), req.full_url, req.data))
            if req.full_url.endswith("/health"):
                return FakeResponse(b'{"status":"ok"}')
            if req.full_url.endswith("/studio"):
                return FakeResponse(b"<h1>Mission Studio</h1>")
            if req.full_url.endswith("/api/v1/studio/geo-objects"):
                return FakeResponse(json.dumps({"objects":[sample_record()]}).encode())
            if req.full_url.endswith("/api/v1/studio/survey/preview"):
                assert req.get_method() == "POST"
                payload = json.loads(req.data)
                assert payload["polygon"]["kind"] == "polygon"
                response = generate_survey_preview(SurveyPlanRequest.model_validate(payload))
                return FakeResponse(json.dumps(response).encode())
            raise AssertionError("Unexpected request")

    opener = Opener()
    assert smoke.call_api(opener, "GET", "/health")["status"] == "ok"
    assert smoke.call_api(opener, "GET", "/studio")["ready"] is True
    objects = smoke.call_api(opener, "GET", "/api/v1/studio/geo-objects")
    chosen, _ = smoke.choose_polygon(objects["objects"], 0)
    response = smoke.call_api(opener, "POST", "/api/v1/studio/survey/preview", {
        "polygon": chosen["object"], "spacing_m": 20, "bearing_deg": 0})
    assert smoke.validate_preview(response, chosen["object"])[0] == 4
    assert [x[0] for x in events] == ["GET", "GET", "GET", "POST"]


def test_required_cli_ca_and_parameter_validation():
    assert smoke.main(["--ca", "/never/a/real/ca.crt"]) == 1
    with pytest.raises(SystemExit):
        smoke.main(["--ca", "ca.crt", "--spacing", "0"])
