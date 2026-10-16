import httpx
import pytest
from aeronexus.providers import ProviderConfig, ProviderKind
from aeronexus.read_only_transport import ReadOnlyTransport, ReadOnlyTransportError

PATH = "/openapi/v2.0/project"
CONFIG = ProviderConfig(ProviderKind.PUBLIC_V2, "https://dji.example", "secret")

def transport():
    return ReadOnlyTransport(CONFIG, frozenset({PATH}))

@pytest.mark.parametrize("path", [
    "http://evil.test", "//evil.test/x", "/openapi/v2.0/../secret",
    "/openapi/v2.0/a?b=1", "/openapi/v2.0/a#x",
    "/openapi/v2.0/a%2fb", "/openapi/v2.0/a\\b", "/openapi/v1/project",
])
def test_reject_unsafe_paths(path):
    with pytest.raises(ValueError):
        ReadOnlyTransport(CONFIG, frozenset({path}))

def test_reject_unapproved_path():
    import asyncio
    with pytest.raises(ReadOnlyTransportError):
        asyncio.run(transport().get("/openapi/v2.0/other"))

def test_reject_cloud_provider():
    c = ProviderConfig(ProviderKind.CLOUD_API, "https://dji.example", "secret")
    with pytest.raises(ValueError):
        ReadOnlyTransport(c, frozenset({PATH}))

def test_reject_empty_allowlist():
    with pytest.raises(ValueError):
        ReadOnlyTransport(CONFIG, frozenset())

@pytest.mark.parametrize("params", [{"bad": object()}, {"ok": True}, {"": "x"}, "invalid"])
def test_reject_bad_params(params):
    import asyncio
    with pytest.raises(ValueError):
        asyncio.run(transport().get(PATH, params))

def test_get_approved_read_only(monkeypatch):
    import asyncio
    captured = {}
    class Client:
        def __init__(self, **kwargs):
            captured.update(kwargs)
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def get(self, path, **kwargs):
            captured["path"] = path
            captured["headers"] = kwargs["headers"]
            return httpx.Response(200, json={"code": 0, "data": {"list": []}},
                                  request=httpx.Request("GET", "https://dji.example" + path))
    monkeypatch.setattr(httpx, "AsyncClient", Client)
    result = asyncio.run(transport().get(PATH))
    assert result["code"] == 0
    assert captured["path"] == PATH
    assert captured["headers"]["X-User-Token"] == "secret"
    assert captured["follow_redirects"] is False
    assert captured["trust_env"] is False

@pytest.mark.parametrize("payload", [{"code": 1}, {"code": True}, [], {"data": {}}])
def test_reject_invalid_responses(monkeypatch, payload):
    import asyncio
    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def get(self, path, **kwargs):
            return httpx.Response(200, json=payload,
                                  request=httpx.Request("GET", "https://dji.example" + path))
    monkeypatch.setattr(httpx, "AsyncClient", Client)
    with pytest.raises(ReadOnlyTransportError):
        asyncio.run(transport().get(PATH))
