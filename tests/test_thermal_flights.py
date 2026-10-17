"""Thermal flight analysis: grouping, background SDK job, ranking, cache and API."""
import importlib

import pytest
from fastapi.testclient import TestClient

from aeronexus.minio_media_index import media_id
from aeronexus.thermal_flights import ThermalFlights, ThermalJobRunning, group_flights
from aeronexus.thermal_geo import ThermalGeoIndex

from test_thermal import HEADERS, PREVIEW, THERMAL, TOKEN, rjpeg
from test_thermal import sdk_dir, service  # noqa: F401  (pytest fixtures)


def row(i, when):
    return {"id": f"{i:064x}", "captured_at": when}


def test_group_flights_splits_on_gap_and_orders_newest_first():
    rows = [row(1, "2026-10-01T10:00:00+02:00"), row(2, "2026-10-01T10:14:00+02:00"),
            row(3, "2026-10-01T10:40:00+02:00"), row(4, None), row(5, "kaputt"),
            row(6, "2026-10-01T08:20:00Z")]  # = 10:20 local, inside the first flight
    flights = group_flights(rows)
    assert [len(f["images"]) for f in flights] == [1, 3]
    assert flights[1]["id"] == f"{1:064x}" and flights[0]["id"] == f"{3:064x}"
    assert flights[1]["start"].startswith("2026-10-01T10:00")


@pytest.fixture
def flights(service):
    ThermalGeoIndex(service.index).scan(service.client, "dji-cloud")
    return ThermalFlights(service)


def test_job_measures_flight_ranks_and_feeds_the_map(flights):
    listing = flights.flights()["flights"]
    assert len(listing) == 1 and listing[0]["images"] == 2 and listing[0]["analyzed"] == 0
    fid = listing[0]["id"]
    job = flights.start(fid)
    assert job["state"] == "running" and job["total"] == 2
    flights.wait(30)
    job = flights.job()
    assert (job["state"], job["processed"], job["measured"], job["skipped"], job["failed"]) == (
        "done", 2, 1, 1, 0)  # the preview image has no radiometric data
    detail = flights.flight_detail(fid)
    assert detail["analyzed"] == 1 and detail["pending"] == 1
    top = detail["ranking"][0]
    assert top["id"] == media_id("dji-cloud", THERMAL) and top["max_c"] == 27.0
    assert top["delta_k"] == pytest.approx(27.0 - 24.0)  # nearest-rank median of 20..27
    items = {i["id"]: i for i in flights.map_items()["items"]}
    assert items[media_id("dji-cloud", THERMAL)]["stats"]["max_c"] == 27.0
    assert items[media_id("dji-cloud", THERMAL)]["flight_id"] == fid
    assert flights.start(fid)["total"] == 1  # measured images are skipped next time
    flights.wait(30)


def test_stats_are_invalidated_when_the_object_changes(flights, service):
    item = media_id("dji-cloud", THERMAL)
    service.analysis(item)  # interactive default-parameter measurement feeds the cache
    assert flights.flights()["flights"][0]["analyzed"] == 1
    service.client.items[THERMAL] = (rjpeg(), "replaced")
    service.index.scan(service.client, "dji-cloud")
    ThermalGeoIndex(service.index).scan(service.client, "dji-cloud")
    assert flights.flights()["flights"][0]["analyzed"] == 0


def test_override_measurements_do_not_overwrite_the_summary(flights, service):
    from aeronexus.thermal_sdk import MeasureParams
    item = media_id("dji-cloud", THERMAL)
    service.analysis(item, MeasureParams(emissivity=0.5))
    assert flights.flights()["flights"][0]["analyzed"] == 0


def test_single_job_and_cancel(flights):
    fid = flights.flights()["flights"][0]["id"]
    flights._job = {"state": "running"}
    with pytest.raises(ThermalJobRunning):
        flights.start(fid)
    flights._job = {"state": "idle"}
    flights._cancel.set()
    assert flights.cancel()["state"] == "idle"


@pytest.fixture
def client(flights, service, monkeypatch):
    app = importlib.import_module("aeronexus.app").app
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    service.flights = flights
    monkeypatch.setattr(app.state, "thermal_service", service, raising=False)
    return TestClient(app)


def test_api(client, flights):
    assert client.get("/api/v1/thermal/flights").status_code == 401
    listing = client.get("/api/v1/thermal/flights", headers=HEADERS).json()
    fid = listing["flights"][0]["id"]
    assert listing["job"]["state"] == "idle" and listing["gap_minutes"] == 15
    r = client.post(f"/api/v1/thermal/flights/{fid}/analyze", headers=HEADERS)
    assert r.status_code == 202 and r.json()["state"] == "running"
    flights.wait(30)
    assert client.get("/api/v1/thermal/jobs/current", headers=HEADERS).json()["state"] == "done"
    detail = client.get(f"/api/v1/thermal/flights/{fid}", headers=HEADERS).json()
    assert detail["ranking"][0]["max_c"] == 27.0 and "object_key" not in repr(detail)
    assert client.get("/api/v1/thermal/flights/" + "0" * 64, headers=HEADERS).status_code == 404
    assert client.get("/api/v1/thermal/flights/not-an-id", headers=HEADERS).status_code == 404
    assert client.post("/api/v1/thermal/flights/" + "0" * 64 + "/analyze",
                       headers=HEADERS).status_code == 404
    assert client.post("/api/v1/thermal/jobs/current/cancel", headers=HEADERS).status_code == 200
    m = client.get("/api/v1/thermal/map", headers=HEADERS).json()
    assert any(i["stats"] for i in m["items"])
    flights._job = {"state": "running"}
    assert client.post(f"/api/v1/thermal/flights/{fid}/analyze", headers=HEADERS).status_code == 409
    flights._job = {"state": "idle"}


def test_page_has_flight_tab_and_thermal_naming():
    from aeronexus.thermal_page import render_thermal_page
    html = render_thermal_page()
    assert 'id="tab-flights"' in html and 'id="map-color"' in html and 'id="map-thermal"' in html
    assert "<title>AeroNexusAdvanced · Thermal</title>" in html and "Thermografie" not in html
    from aeronexus.dji_media_page import render_dji_media_page
    from aeronexus.multispectral_page import render_multispectral_page
    from aeronexus.operations_page import render_operations
    from aeronexus.status_page import render_page
    from aeronexus.studio_page import render_studio
    for page in (render_operations(), render_studio(), render_page(30), render_dji_media_page(),
                 render_multispectral_page()):
        assert "Thermografie" not in page and '/thermal">Thermal' in page.replace(
            ' style="color:#9edaff;padding:9px;text-decoration:none"', "").replace(
            ' style="color:#9cd2ff"', "")
