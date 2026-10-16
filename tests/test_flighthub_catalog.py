"""FlightHub project library (waylines, models, tasks, track) and its API."""
import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from aeronexus import app as app_module
from aeronexus.flighthub_catalog import (
    CatalogError, normalize_models, normalize_tasks, normalize_waylines, read_catalog,
    read_task_track, track_geojson,
)
from aeronexus.flighthub_poller import FlightHubFleetRefresher, FlightHubPollSettings
from aeronexus.status_runtime import StatusRuntime
from test_flighthub_fleet import CATALOG_PAYLOADS, ENV, OC, PC, PROJECT, TASK, fake_get  # noqa: F401


TOKEN = "aeronexus-status-token-not-dji-secret-123456"


def test_waylines_drop_signed_urls_and_unknown_types():
    (w,) = normalize_waylines(CATALOG_PAYLOADS["/openapi/v2.0/wayline"]())
    assert w == {"id": "w1", "name": "Dach Nord", "template_types": ["mapping_2d"],
                 "device_model_key": "0-99-1", "lenses": ["ir", "wide"],
                 "updated_at": 1760000000, "size_bytes": 2048}
    assert "signed" not in json.dumps(w)


def test_models_and_tasks():
    (m,) = normalize_models(CATALOG_PAYLOADS["/openapi/v2.0/model"]())
    assert m["file_type"] == "model_3d" and m["show_on_map"] is True
    tasks = normalize_tasks(CATALOG_PAYLOADS["/openapi/v2.0/flight-task/list"]())
    assert [t["uuid"] for t in tasks] == [TASK]  # invalid UUID skipped
    assert tasks[0]["status"] == "success" and tasks[0]["exceptions"] == 1
    assert "DOCKSN" not in json.dumps(tasks)


def test_null_lists_and_errors():
    for normalize in (normalize_waylines, normalize_models, normalize_tasks):
        assert normalize({"code": 0, "data": {"list": None}}) == ()
        for bad in ({"code": 1}, {"code": 0}, {"code": 0, "data": {"list": "x"}}):
            with pytest.raises(CatalogError):
                normalize(bad)


def test_track_geojson_filters_invalid_points_and_serial():
    feature = track_geojson(CATALOG_PAYLOADS[f"/openapi/v2.0/flight-task/{TASK}/track"]())
    assert feature["geometry"]["coordinates"] == [[8.5, 49.1, 40.5], [8.6, 49.2, 41]]
    assert feature["properties"] == {"name": "Inspektion", "flight_distance": 512,
                                     "flight_duration": 300, "points": 2}
    assert "SECRET-SN" not in json.dumps(feature)


def test_read_catalog_is_best_effort(monkeypatch):
    from aeronexus.read_only_transport import BusinessError, ReadOnlyTransport
    async def get(self, path, params=None, *, project_uuid=None):
        if path == "/openapi/v2.0/model":
            raise BusinessError("x", business_code=1)
        if path == "/openapi/v2.0/flight-task/list":
            assert params["end_at"] - params["begin_at"] == 30 * 86400
        return CATALOG_PAYLOADS[path]()
    monkeypatch.setattr(ReadOnlyTransport, "get", get)
    catalog = asyncio.run(read_catalog(PC, PROJECT))
    assert catalog["models"] is None and len(catalog["waylines"]) == 1 and len(catalog["tasks"]) == 1


def test_catalog_public_only_and_task_uuid_validated():
    with pytest.raises(CatalogError):
        asyncio.run(read_catalog(OC, PROJECT))
    with pytest.raises(CatalogError):
        asyncio.run(read_task_track(PC, PROJECT, "../x"))


def test_refresher_catalog_interval(fake_get):
    runtime = StatusRuntime()
    refresher = FlightHubFleetRefresher(runtime, FlightHubPollSettings.from_env(ENV))
    asyncio.run(refresher())
    asyncio.run(refresher())
    assert sum(path == "/openapi/v2.0/wayline" for path, _ in fake_get) == 1  # 600 s interval
    summary = runtime.summary()["flighthub"]
    assert summary["system_status"] == "ok"
    assert (summary["waylines"], summary["models"], summary["tasks"]) == (1, 1, 1)
    assert "Dach Nord" not in json.dumps(runtime.summary())


def test_catalog_settings():
    assert FlightHubPollSettings.from_env(ENV).catalog_interval_seconds == 600
    assert FlightHubPollSettings.from_env({**ENV, "AERONEXUS_FH_CATALOG_SECONDS": "0"}).catalog_interval_seconds == 0
    for bad in ("30", "x", "100000"):
        with pytest.raises(ValueError):
            FlightHubPollSettings.from_env({**ENV, "AERONEXUS_FH_CATALOG_SECONDS": bad})


def test_catalog_off_makes_no_library_calls(fake_get):
    settings = FlightHubPollSettings.from_env({**ENV, "AERONEXUS_FH_CATALOG_SECONDS": "0"})
    asyncio.run(FlightHubFleetRefresher(StatusRuntime(), settings)())
    assert not any(path in ("/openapi/v2.0/wayline", "/openapi/v2.0/system_status")
                   for path, _ in fake_get)


@pytest.fixture
def api(monkeypatch, fake_get):
    monkeypatch.setattr(app_module.app.state, "status_runtime", StatusRuntime())
    monkeypatch.delenv("AERONEXUS_CLOUD_MQTT_ENABLED", raising=False)
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    with TestClient(app_module.app) as client:
        refresher = app_module.app.state.flighthub
        asyncio.run(refresher())  # deterministic first refresh
        yield client, fake_get


AUTH = {"Authorization": "Bearer " + TOKEN}


def test_catalog_endpoint_requires_token(api):
    client, _ = api
    assert client.get("/api/v1/flighthub/catalog").status_code == 401
    body = client.get("/api/v1/flighthub/catalog", headers=AUTH).json()
    (project,) = body["projects"]
    assert project["name"] == "Survey" and project["waylines"][0]["name"] == "Dach Nord"
    assert "secret-org-key" not in json.dumps(body)


def test_track_endpoint_known_task_cached(api):
    client, calls = api
    url = f"/api/v1/flighthub/projects/{PROJECT}/tasks/{TASK}/track"
    assert client.get(url).status_code == 401
    first = client.get(url, headers=AUTH)
    assert first.status_code == 200 and first.headers["content-type"] == "application/geo+json"
    assert first.headers["cache-control"] == "no-store"
    assert first.json()["geometry"]["type"] == "LineString"
    client.get(url, headers=AUTH)
    assert sum(path.endswith("/track") for path, _ in calls) == 1


def test_track_endpoint_rejects_unknown_ids(api):
    client, calls = api
    other = "e7b81eec-f182-473a-9368-9e220e46f9d9"
    for url in (f"/api/v1/flighthub/projects/{PROJECT}/tasks/{other}/track",
                f"/api/v1/flighthub/projects/{other}/tasks/{TASK}/track"):
        assert client.get(url, headers=AUTH).status_code == 404
    assert not any(path.endswith("/track") for path, _ in calls)


def test_track_endpoint_hides_provider_errors(api, monkeypatch):
    from aeronexus.read_only_transport import ReadOnlyTransport
    client, _ = api
    async def failing(self, path, params=None, *, project_uuid=None):
        raise RuntimeError("upstream secret detail")
    monkeypatch.setattr(ReadOnlyTransport, "get", failing)
    res = client.get(f"/api/v1/flighthub/projects/{PROJECT}/tasks/{TASK}/track", headers=AUTH)
    assert res.status_code == 502 and "secret" not in res.text


def test_track_endpoint_without_flighthub(monkeypatch):
    monkeypatch.setattr(app_module.app.state, "status_runtime", StatusRuntime())
    monkeypatch.delenv("AERONEXUS_FH_POLL_ENABLED", raising=False)
    monkeypatch.delenv("AERONEXUS_CLOUD_MQTT_ENABLED", raising=False)
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    with TestClient(app_module.app) as client:
        res = client.get(f"/api/v1/flighthub/projects/{PROJECT}/tasks/{TASK}/track", headers=AUTH)
        assert res.status_code == 404
        assert client.get("/api/v1/flighthub/catalog", headers=AUTH).json()["projects"] == []
