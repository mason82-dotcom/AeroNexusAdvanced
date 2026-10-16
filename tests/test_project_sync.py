import asyncio
import httpx
import pytest
from aeronexus.inventory import Inventory
from aeronexus.project_sync import (ProjectSyncError, _project_path,
                                    fetch_projects, parse_projects, register_projects)
from aeronexus.providers import ProviderConfig, ProviderKind

PUBLIC = ProviderKind.PUBLIC_V2
ONPREM = ProviderKind.ONPREM_V2
ORG = "a1b2c3d4-5678-9012-abcd-ef1234567890"

def test_paths():
    assert _project_path(PUBLIC, None) == "/openapi/v2.0/project"
    assert _project_path(ONPREM, ORG).endswith(f"/organizations/{ORG}/projects")

@pytest.mark.parametrize("org", [None, "invalid", "../foo", ""])
def test_reject_invalid_org(org):
    with pytest.raises(ValueError):
        _project_path(ONPREM, org)

def test_reject_cloud_api():
    with pytest.raises(ValueError):
        _project_path(ProviderKind.CLOUD_API, None)

def test_parse_and_register():
    projects = parse_projects(PUBLIC, {"code": 0, "data": {"list": [
        {"uuid": "p1", "name": "Mission A"}]}})
    inventory = Inventory()
    assert register_projects(inventory, projects) == 1
    assert inventory.projects(PUBLIC)[0].name == "Mission A"

@pytest.mark.parametrize("payload", [
    {"code": 1001, "data": {"list": []}},
    {"code": 0, "data": {}},
    {"code": 0, "data": {"list": [{}]}},
    {"code": 0, "data": {"list": "wrong"}},
])
def test_invalid_responses(payload):
    with pytest.raises(ProjectSyncError):
        parse_projects(PUBLIC, payload)

@pytest.mark.parametrize("page,size", [(0, 20), (1, 0), (1, 101)])
def test_invalid_pagination(page, size):
    config = ProviderConfig(PUBLIC, "https://example.com", "secret")
    with pytest.raises(ValueError):
        asyncio.run(fetch_projects(config, page=page, page_size=size))

def test_fetch_public_mock(monkeypatch):
    async def fake_get(self, path, headers, params):
        assert path == "/openapi/v2.0/project"
        assert headers["X-User-Token"] == "secret"
        assert params["page"] == 2
        return httpx.Response(200, json={"code": 0, "data": {"list": [
            {"uuid": "p1", "name": "Mission A"}]}},
            request=httpx.Request("GET", "https://example.com"+path))
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    config = ProviderConfig(PUBLIC, "https://example.com", "secret")
    assert asyncio.run(fetch_projects(config, page=2))[0].project_id == "p1"

def test_fetch_onprem_mock(monkeypatch):
    async def fake_get(self, path, headers, params):
        assert path.endswith(f"/organizations/{ORG}/projects")
        return httpx.Response(200, json={"code": 0, "data": {"list": []}},
            request=httpx.Request("GET", "https://example.com"+path))
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    config = ProviderConfig(ONPREM, "https://example.com", "secret")
    assert asyncio.run(fetch_projects(config, ORG)) == ()
