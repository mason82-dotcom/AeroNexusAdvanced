import asyncio
import httpx
import pytest
from aeronexus.flighthub_v2 import FlightHubV2, FlightHubError
from aeronexus.providers import ProviderConfig, ProviderKind

def client(kind):
    return FlightHubV2(ProviderConfig(kind, "https://example.com", "secret-token"))

def test_reject_cloud_api():
    with pytest.raises(ValueError):
        client(ProviderKind.CLOUD_API)

def test_public_status_mock(monkeypatch):
    async def fake_get(self, path, headers):
        assert path == "/openapi/v2.0/system_status"
        assert headers["X-User-Token"] == "secret-token"
        assert headers["X-Language"] == "en"
        assert headers["X-Request-Id"]
        return httpx.Response(200, json={"code": 0, "message": ""},
                              request=httpx.Request("GET", "https://example.com"+path))
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    assert asyncio.run(client(ProviderKind.PUBLIC_V2).system_status())["code"] == 0

def test_onprem_health_mock(monkeypatch):
    async def fake_get(self, path, headers):
        assert path == "/openapi/v2.0/drc/health"
        assert headers["X-Project-Uuid"] == "project-1"
        return httpx.Response(200, json={"code": 0, "message": "OK", "data": None},
                              request=httpx.Request("GET", "https://example.com"+path))
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    assert asyncio.run(client(ProviderKind.ONPREM_V2).realtime_control_health("project-1"))["code"] == 0

def test_wrong_provider_method():
    with pytest.raises(ValueError):
        asyncio.run(client(ProviderKind.ONPREM_V2).system_status())
    with pytest.raises(ValueError):
        asyncio.run(client(ProviderKind.PUBLIC_V2).realtime_control_health("project-1"))

def test_reject_bad_business_code(monkeypatch):
    async def fake_get(self, path, headers):
        return httpx.Response(200, json={"code": 1001, "message": "failure"},
                              request=httpx.Request("GET", "https://example.com"+path))
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    with pytest.raises(FlightHubError):
        asyncio.run(client(ProviderKind.PUBLIC_V2).system_status())
