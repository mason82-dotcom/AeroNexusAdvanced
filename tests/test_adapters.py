import asyncio
import httpx
import pytest
from aeronexus.adapters import DJIAdapter

@pytest.mark.parametrize("url", ["http://example.com", "https://user:pass@example.com",
    "file:///etc/passwd", "https://example.com/other", "https://example.com?x=1"])
def test_reject_unsafe_base_url(url):
    with pytest.raises(ValueError):
        DJIAdapter(url, "token")

@pytest.mark.parametrize("path", ["//evil.example/path", "/../secret", "/./secret",
    "/ok#fragment", "/foo\\bar", "https://evil.example/"])
def test_reject_invalid_path(path):
    adapter = DJIAdapter("https://example.com", "token")
    with pytest.raises(ValueError):
        asyncio.run(adapter.get(path))

def test_get_success_and_headers(monkeypatch):
    async def fake_get(self, path, headers):
        assert path == "/api/test"
        assert headers == {"X-User-Token": "secret", "X-Project-Uuid": "project"}
        return httpx.Response(200, json={"code": 0, "data": {"ok": True}},
                              request=httpx.Request("GET", "https://example.com/api/test"))
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    result = asyncio.run(DJIAdapter("https://example.com", "secret").get("/api/test", "project"))
    assert result["data"]["ok"] is True

def test_business_error(monkeypatch):
    async def fake_get(self, path, headers):
        return httpx.Response(200, json={"code": 401, "message": "denied"},
                              request=httpx.Request("GET", "https://example.com/api/test"))
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    with pytest.raises(ValueError, match="business API"):
        asyncio.run(DJIAdapter("https://example.com", "secret").get("/api/test"))

def test_http_error(monkeypatch):
    async def fake_get(self, path, headers):
        return httpx.Response(401, json={"error": "unauthorized"},
                              request=httpx.Request("GET", "https://example.com/api/test"))
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(DJIAdapter("https://example.com", "secret").get("/api/test"))
