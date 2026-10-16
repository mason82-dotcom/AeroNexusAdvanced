"""DJI Cloud API 2 official SDK skeleton BFF read-only integration.

All tests use local fixtures. Never contact DJI or an SDK backend.
"""
from datetime import datetime, timezone
import asyncio

from fastapi.testclient import TestClient
import httpx
import pytest

from aeronexus.app import app
from aeronexus.cloud_api2_bridge import (
    CloudApi2Bridge, CloudApi2BridgeError, CloudApi2Settings, normalize_devices,
)


TOKEN = "aeronexus-cloud-api2-test-token-000000"
NOW = datetime(2026, 10, 16, 15, 0, tzinfo=timezone.utc)
DRONE = {
    "sn": "M4TEXAMPLE001",
    "deviceType": "DRONE",
    "model": "Matrice 4T",
    "name": "<script>test</script>",
    "online": True,
    "lastOsd": {"attributes": {
        "latitude": 49.1533, "longitude": 8.58417,
        "battery_percent": 81, "altitude": 52.5,
        "speed": 4.2, "mode": "Waypoint",
    }},
    "lastOsdAt": "2026-10-16T14:59:57Z",
    "recentHms": [
        {"alertCode": "HMS0001", "level": "WARNING", "message": "Testwarnung",
         "timestamp": "2026-10-16T14:59:57Z"}
    ],
    "childDevices": [],
}


def test_opt_in_and_private_https_url_validation():
    assert CloudApi2Settings.from_env({}) is None
    assert CloudApi2Settings.from_env({"AERONEXUS_CLOUDAPI2_ENABLED": "0"}) is None
    cfg = CloudApi2Settings.from_env({
        "AERONEXUS_CLOUDAPI2_ENABLED": "1",
        "AERONEXUS_CLOUDAPI2_BFF_URL": "https://192.168.178.90:8443",
        "AERONEXUS_CLOUDAPI2_BFF_TOKEN": TOKEN,
    })
    assert cfg.base_url == "https://192.168.178.90:8443"
    assert TOKEN not in repr(cfg)
    assert cfg.stale_after_seconds == 45


@pytest.mark.parametrize("url", [
    "http://192.168.178.90", "https://8.8.8.8",
    "https://example.org", "file:///etc/passwd",
    "https://private.lan/api/v1/", "https://private.lan?secret=1",
    "https://user:pass@192.168.178.90", "https://192.168.178.90:99999",
    "https://evil.invalid",
])
def test_cloud2_rejects_unsafe_upstream_addresses(url):
    with pytest.raises((CloudApi2BridgeError, ValueError)):
        CloudApi2Settings(base_url=url, api_token=TOKEN)


def test_cloud2_allows_loopback_http_for_dev_bff_only():
    assert CloudApi2Settings("http://127.0.0.1:8080", TOKEN).base_url.startswith("http:")
    assert CloudApi2Settings("https://cloudserver.lan", TOKEN).base_url.startswith("https:")


def test_cloud2_requires_service_authentication():
    for secret in ("", "short", "invalid whitespace in token"):
        with pytest.raises(CloudApi2BridgeError):
            CloudApi2Settings("https://192.168.178.90", secret)


def test_normalize_only_drone_not_dock_and_fresh_values():
    records = normalize_devices([
        {"sn": "DOCKFAKE01", "deviceType": "DOCK", "online": True,
         "childDevices": [DRONE]},
        DRONE,  # SDK may flatten nested objects and also list top-level.
        {"sn": "RC000", "deviceType": "REMOTE_CONTROLLER", "online": True},
    ], now=NOW)
    assert len(records) == 1
    drone = records[0]
    assert drone["device_id"] == "M4TEXAMPLE001"
    assert drone["provider"] == "dji-cloud-api-2"
    assert drone["kind"] == "aircraft"
    assert drone["project_id"] == "cloud-api-2"
    assert drone["online"] is True
    assert drone["freshness"] == "fresh"
    assert drone["age_seconds"] == 3
    assert drone["telemetry"]["latitude"] == 49.1533
    assert drone["telemetry"]["flight_mode_label"] == "Waypoint"
    assert "flight_mode_code" not in drone["telemetry"]
    assert drone["health"][0]["code"] == "HMS0001"
    assert drone["health"][0]["level"] == "warning"
    assert "DOCKFAKE01" not in str(records)


def test_cloud2_never_invents_a_valid_gps_fix():
    device = {**DRONE, "lastOsd": {"attributes": {
        "latitude": 0, "longitude": 0, "battery_percent": 99,
    }}}
    rows = normalize_devices([device], now=NOW)
    assert rows[0]["telemetry"]["latitude"] is None
    assert rows[0]["telemetry"]["longitude"] is None


def test_cloud2_missing_telemetry_is_not_marked_as_live():
    row = {**DRONE, "lastOsd": None, "lastOsdAt": None}
    result = normalize_devices([row], now=NOW)
    assert result[0]["freshness"] == "missing"
    assert result[0]["online"] is None
    assert result[0]["telemetry"]["battery_percent"] is None


def test_cloud2_stale_and_clock_skew_cannot_appear_live():
    old = {**DRONE, "lastOsdAt": "2026-10-16T14:00:00Z"}
    future = {**DRONE, "lastOsdAt": "2026-10-16T16:00:00Z",
              "sn": "M4TEXAMPLE002"}
    rows = normalize_devices([old, future], now=NOW)
    assert [r["freshness"] for r in rows] == ["stale", "clock_skew"]
    assert all(r["online"] is None for r in rows)


def test_cloud2_invalid_framing_rejected():
    for payload in ({}, None, "invalid", [None]):
        with pytest.raises(CloudApi2BridgeError):
            normalize_devices(payload, now=NOW)
    bad = {**DRONE, "lastOsd": {"other": "value"}}
    with pytest.raises(CloudApi2BridgeError):
        normalize_devices([bad], now=NOW)


def test_cloud2_invalid_hms_payload_is_ignored():
    result = normalize_devices([{**DRONE, "recentHms": [
        {}, {"alertCode": "X", "level": "warn", "url": "http://secret"},
    ]}], now=NOW)
    assert result[0]["health"] == [
        {"code": "X", "level": "notification", "message": None, "timestamp": None},
    ]
    assert "secret" not in str(result)


def test_cloud2_bridge_fetches_exactly_one_read_only_path(monkeypatch):
    calls = []
    real_client = httpx.AsyncClient

    def backend(request):
        calls.append((request.method, request.url.path, request.headers["authorization"]))
        return httpx.Response(200, json=[{
            **DRONE, "lastOsdAt": datetime.now(timezone.utc).isoformat(),
        }])

    def client_factory(**kwargs):
        assert kwargs["follow_redirects"] is False
        assert kwargs["trust_env"] is False
        assert kwargs["verify"] is True
        return real_client(transport=httpx.MockTransport(backend), **kwargs)

    monkeypatch.setattr("aeronexus.cloud_api2_bridge.httpx.AsyncClient", client_factory)
    bridge = CloudApi2Bridge(CloudApi2Settings("https://192.168.178.90", TOKEN))
    result = asyncio.run(bridge.read())
    again = asyncio.run(bridge.read())
    assert result["state"] == again["state"] == "ok"
    assert result["total"] == again["total"] == 1
    assert len(calls) == 1
    assert calls[0] == ("GET", "/api/v1/devices", "Bearer " + TOKEN)
    assert TOKEN not in str(result)


def test_cloud2_bff_failure_is_sanitized(monkeypatch):
    real_client = httpx.AsyncClient

    def client_factory(**kwargs):
        return real_client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(401, json={"message": "secret private backend"})
            ),
            **kwargs,
        )

    monkeypatch.setattr("aeronexus.cloud_api2_bridge.httpx.AsyncClient", client_factory)
    bridge = CloudApi2Bridge(CloudApi2Settings("https://192.168.178.90", TOKEN))
    result = asyncio.run(bridge.read())
    assert result == {"source": "dji-cloud-api-2", "state": "unavailable",
                      "devices": [], "total": 0}
    assert TOKEN not in str(result)
    assert "secret private backend" not in str(result)


def test_cloud2_response_size_bounded_before_loading(monkeypatch):
    real_client = httpx.AsyncClient

    def client_factory(**kwargs):
        return real_client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, content=b"X" * (1024 * 1024))
            ),
            **kwargs,
        )

    monkeypatch.setattr("aeronexus.cloud_api2_bridge.httpx.AsyncClient", client_factory)
    bridge = CloudApi2Bridge(CloudApi2Settings("https://192.168.178.90", TOKEN))
    result = asyncio.run(bridge.read())
    assert result["state"] == "unavailable"
    assert result["devices"] == []


def test_cloud2_cache_recomputes_freshness_without_new_request(monkeypatch):
    calls = []
    real_client = httpx.AsyncClient

    def backend(_):
        calls.append(1)
        return httpx.Response(200, json=[{
            **DRONE, "lastOsdAt": datetime.now(timezone.utc).isoformat(),
        }])

    def client_factory(**kwargs):
        return real_client(transport=httpx.MockTransport(backend), **kwargs)

    monkeypatch.setattr("aeronexus.cloud_api2_bridge.httpx.AsyncClient", client_factory)
    bridge = CloudApi2Bridge(CloudApi2Settings("https://192.168.178.90", TOKEN))
    first = asyncio.run(bridge.read())
    assert first["devices"][0]["online"] is True
    assert first["devices"][0]["reported_online"] is True
    bridge._cached[0]["received_at"] = "2026-10-16T10:00:00Z"
    stale = asyncio.run(bridge.read())
    assert len(calls) == 1
    assert stale["state"] == "ok"
    assert stale["devices"][0]["freshness"] == "stale"
    assert stale["devices"][0]["online"] is None
    assert stale["devices"][0]["reported_online"] is True


def test_cloud2_endpoint_disabled_by_default_and_private(monkeypatch):
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", "aeronexus-unit-dashboard-token-123456789")
    with TestClient(app) as client:
        assert client.get("/api/v1/cloudapi2/devices").status_code == 401
        res = client.get("/api/v1/cloudapi2/devices", headers={
            "Authorization": "Bearer aeronexus-unit-dashboard-token-123456789"})
        assert res.status_code == 200
        assert res.json() == {"source": "dji-cloud-api-2", "state": "disabled",
                              "devices": [], "total": 0}
        assert res.headers["cache-control"] == "no-store"
