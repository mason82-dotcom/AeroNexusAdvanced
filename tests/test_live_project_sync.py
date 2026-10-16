import asyncio
import pytest
from aeronexus.inventory import Inventory, Project
from aeronexus.live_project_sync import project_list_path, read_project_page, sync_project_page
from aeronexus.providers import ProviderConfig, ProviderKind
from aeronexus.read_only_transport import ReadOnlyTransport

K = ProviderKind.PUBLIC_V2
C = ProviderConfig(K, "https://dji.example", "secret")
ORG = "105ddd05-34ce-46b6-a872-cb32b8c98f64"

def test_documented_paths():
    assert project_list_path(K) == "/openapi/v2.0/project"
    assert project_list_path(ProviderKind.ONPREM_V2, ORG).endswith(f"/organizations/{ORG}/projects")

@pytest.mark.parametrize("org", [None, "", "../bad"])
def test_invalid_organization(org):
    with pytest.raises(ValueError):
        project_list_path(ProviderKind.ONPREM_V2, org)

def test_reject_cloud_api():
    with pytest.raises(ValueError):
        project_list_path(ProviderKind.CLOUD_API)

@pytest.mark.parametrize("page,size", [(0,20),(1,0),(1,101),(True,20),(1,False)])
def test_reject_pagination(page,size):
    with pytest.raises(ValueError):
        asyncio.run(read_project_page(C, page=page, page_size=size))

def test_live_read_uses_allowlisted_get(monkeypatch):
    seen = {}
    async def fake_get(self, path, params=None):
        seen["path"] = path
        seen["params"] = params
        return {"code": 0, "data": {"list": [{"uuid": "p1", "name": "Mission"}]}}
    monkeypatch.setattr(ReadOnlyTransport, "get", fake_get)
    projects = asyncio.run(read_project_page(C))
    assert len(projects) == 1 and projects[0].project_id == "p1"
    assert seen["path"] == "/openapi/v2.0/project"
    assert seen["params"]["page"] == 1

def test_sync_into_inventory(monkeypatch):
    async def fake_get(self, path, params=None):
        return {"code": 0, "data": {"list": [{"uuid": "p1", "name": "Mission"}]}}
    monkeypatch.setattr(ReadOnlyTransport, "get", fake_get)
    inv = Inventory()
    assert asyncio.run(sync_project_page(inv, C)) == 1
    assert inv.projects(K) == (Project(K, "p1", "Mission"),)

def test_conflict_is_atomic(monkeypatch):
    async def fake_get(self, path, params=None):
        return {"code": 0, "data": {"list": [
            {"uuid": "p2", "name": "New"},
            {"uuid": "p1", "name": "Changed"}]}}
    monkeypatch.setattr(ReadOnlyTransport, "get", fake_get)
    inv = Inventory()
    inv.add_project(Project(K, "p1", "Original"))
    with pytest.raises(ValueError, match="Conflicting"):
        asyncio.run(sync_project_page(inv, C))
    assert inv.projects(K) == (Project(K, "p1", "Original"),)

def test_duplicate_is_atomic(monkeypatch):
    async def fake_get(self, path, params=None):
        return {"code": 0, "data": {"list": [
            {"uuid": "p1", "name": "Same"}, {"uuid": "p1", "name": "Same"}]}}
    monkeypatch.setattr(ReadOnlyTransport, "get", fake_get)
    inv = Inventory()
    with pytest.raises(ValueError, match="Duplicate"):
        asyncio.run(sync_project_page(inv, C))
    assert inv.projects() == ()
