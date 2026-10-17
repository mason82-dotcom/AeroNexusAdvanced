"""Local DJI Cloud API stack health: loopback-only probes, no credentials, API."""
import asyncio
import importlib

import httpx
import pytest
from fastapi.testclient import TestClient

from aeronexus.cloud_stack import CloudStackHealth, fleet_view, overall, stack_host

APP_MODULE = importlib.import_module("aeronexus.app")
TOKEN = "cloud-stack-test-only-dashboard-token-123456"


def backend(down=()):
    calls = []

    def handle(request: httpx.Request):
        calls.append((request.url.host, request.url.port, request.url.path,
                      "authorization" in request.headers))
        port = request.url.port
        if port in down:
            raise httpx.ConnectError("refused")
        if port == 6789:
            return httpx.Response(401)
        if port == 9997:
            return httpx.Response(200, json={"items": [{"name": "live/x", "ready": True},
                                                       {"name": "live/y", "ready": False}]})
        return httpx.Response(200)
    return handle, calls


async def tcp_up(host, port):
    return {"state": "up", "ms": 1}


async def tcp_down(host, port):
    return {"state": "down"}


def test_host_must_be_loopback():
    assert stack_host({}) == "127.0.0.1"
    for bad in ("192.168.178.63", "example.org", ""):
        with pytest.raises(ValueError):
            stack_host({"AERONEXUS_CLOUD_STACK_HOST": bad})


def test_probes_are_loopback_unauthenticated_and_cached():
    handle, calls = backend()
    health = CloudStackHealth("127.0.0.1", transport=httpx.MockTransport(handle), tcp=tcp_up)
    services = asyncio.run(health.services())
    assert {n: s["state"] for n, s in services.items()} == {
        "api": "up", "mqtt": "up", "minio": "up", "control": "up", "mediamtx": "up"}
    assert services["api"]["http"] == 401 and services["mediamtx"]["streams"] == 1
    assert {c[0] for c in calls} == {"127.0.0.1"} and not any(c[3] for c in calls)
    asyncio.run(health.services())
    assert len(calls) == 4  # second call served from the 10 s cache


def test_down_services_and_overall():
    handle, _ = backend(down={9000, 9997})
    health = CloudStackHealth("127.0.0.1", transport=httpx.MockTransport(handle), tcp=tcp_down)
    services = asyncio.run(health.services())
    assert services["minio"]["state"] == services["mqtt"]["state"] == "down"
    fleet = fleet_view([], {"state": "subscribed"})
    assert overall(services, fleet) == "degraded"
    ok, _ = backend(down={9997})
    services = asyncio.run(CloudStackHealth("127.0.0.1", transport=httpx.MockTransport(ok),
                                            tcp=tcp_up).services())
    assert overall(services, fleet) == "ok"  # MediaMTX is optional
    assert overall(services, fleet_view([], {"state": "auth_failed"})) == "degraded"


def test_fleet_view_only_cloud_devices_without_serials():
    views = [{"provider": "dji-cloud-api", "kind": "aircraft", "name": "M3E", "device_id": "SECRET1",
              "online": True, "freshness": "fresh", "received_at": "t"},
             {"provider": "dji-cloud-api", "kind": "controller", "name": "Remote controller",
              "device_id": "SECRET2", "online": True, "freshness": "stale", "received_at": "t"},
             {"provider": "flighthub2-public-v2", "kind": "aircraft", "name": "FH", "device_id": "X"}]
    fleet = fleet_view(views, {"state": "subscribed", "last_message_at": "t"})
    assert [(d["kind"], d["name"], d["online"]) for d in fleet["devices"]] == [
        ("controller", "Remote controller", None), ("aircraft", "M3E", True)]
    assert "SECRET" not in repr(fleet)


def test_api_and_status_page(monkeypatch):
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    handle, _ = backend()
    monkeypatch.setattr(APP_MODULE.app.state, "cloud_stack_health",
                        CloudStackHealth("127.0.0.1", transport=httpx.MockTransport(handle), tcp=tcp_up),
                        raising=False)
    client = TestClient(APP_MODULE.app)
    assert client.get("/api/v1/cloud/stack").status_code == 401
    data = client.get("/api/v1/cloud/stack", headers={"Authorization": "Bearer " + TOKEN}).json()
    assert data["overall"] in ("ok", "degraded") and set(data["services"]) == {
        "api", "mqtt", "minio", "control", "mediamtx"}
    from aeronexus.status_page import render_page
    page = render_page(15)
    assert 'id="cloud-panel"' in page and "/api/v1/cloud/stack" in page and "innerHTML" not in page
