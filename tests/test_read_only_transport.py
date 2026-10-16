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


@pytest.mark.parametrize("project_uuid", ["../unsafe", "", 42])
def test_reject_invalid_project_uuid(project_uuid):
    import asyncio
    with pytest.raises(ValueError, match="UUID"):
        asyncio.run(transport().get(PATH, project_uuid=project_uuid))


def test_project_uuid_header_for_approved_get(monkeypatch):
    import asyncio
    captured = {}
    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def get(self, path, **kwargs):
            captured.update(kwargs["headers"])
            return httpx.Response(200, json={"code": 0, "data": {"list": []}},
                                  request=httpx.Request("GET", "https://dji.example" + path))
    monkeypatch.setattr(httpx, "AsyncClient", Client)
    project = "93df839d-ae74-4f04-842e-2f1f81c89a66"
    result = asyncio.run(transport().get(PATH, project_uuid=project))
    assert result["code"] == 0
    assert captured["X-Project-Uuid"] == project
    assert captured["X-User-Token"] == "secret"


def _client_with(responses, captured=None):
    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def get(self, path, **kwargs):
            if captured is not None:
                captured.append(kwargs["headers"]["X-Request-Id"])
            status, body, headers = responses.pop(0)
            return httpx.Response(status, json=body, headers=headers,
                                  request=httpx.Request("GET", "https://dji.example" + path))
    return Client


@pytest.mark.parametrize("status,cls", [
    (401, "AuthenticationError"), (403, "PermissionDeniedError"), (404, "NotFoundError"),
])
def test_status_errors_are_classified_without_body(monkeypatch, status, cls):
    import asyncio
    from aeronexus import read_only_transport as rot
    monkeypatch.setattr(httpx, "AsyncClient", _client_with(
        [(status, {"message": "secret detail"}, {})]))
    with pytest.raises(getattr(rot, cls)) as info:
        asyncio.run(transport().get(PATH))
    assert info.value.status_code == status and info.value.request_id
    assert "secret detail" not in str(info.value)
    assert isinstance(info.value, ReadOnlyTransportError)


def test_business_code_error(monkeypatch):
    import asyncio
    from aeronexus.read_only_transport import BusinessError
    monkeypatch.setattr(httpx, "AsyncClient", _client_with([(200, {"code": 210060}, {})]))
    with pytest.raises(BusinessError) as info:
        asyncio.run(transport().get(PATH))
    assert info.value.business_code == 210060


def test_transient_status_retried_with_retry_after(monkeypatch):
    import asyncio
    from aeronexus import read_only_transport as rot
    sleeps, ids = [], []
    async def fake_sleep(seconds):
        sleeps.append(seconds)
    monkeypatch.setattr(rot.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(httpx, "AsyncClient", _client_with([
        (429, {}, {"Retry-After": "2"}), (503, {}, {}), (200, {"code": 0, "data": {}}, {})], ids))
    assert asyncio.run(transport().get(PATH))["code"] == 0
    assert sleeps[0] == 2.0 and len(sleeps) == 2
    assert len(set(ids)) == 1  # one logical request, one request id


def test_retries_are_bounded(monkeypatch):
    import asyncio
    from aeronexus import read_only_transport as rot
    async def fake_sleep(seconds):
        assert seconds <= 30
    monkeypatch.setattr(rot.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(httpx, "AsyncClient", _client_with(
        [(502, {}, {"Retry-After": "999"})] * 3))
    with pytest.raises(rot.ServerError):
        asyncio.run(transport().get(PATH))


def test_v01_paths_allowed_other_versions_not():
    ReadOnlyTransport(CONFIG, frozenset({"/openapi/v0.1/project"}))
    with pytest.raises(ValueError):
        ReadOnlyTransport(CONFIG, frozenset({"/openapi/v1.0/project"}))


def test_business_200401_is_authentication_error(monkeypatch):
    import asyncio
    from aeronexus.read_only_transport import AuthenticationError
    monkeypatch.setattr(httpx, "AsyncClient", _client_with(
        [(200, {"code": 200401, "message": "X-User-Token not found or empty"}, {})]))
    with pytest.raises(AuthenticationError) as info:
        asyncio.run(transport().get(PATH))
    assert info.value.business_code == 200401
    assert "X-User-Token not found" not in str(info.value)
