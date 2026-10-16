"""Read-only FlightHub V2 project listing and normalization.

DJI references:
Public: /openapi/v2.0/project
On-premises: /openapi/v2.0/manage/api/v1/organizations/{uuid}/projects
"""
from uuid import UUID, uuid4
import httpx
from .inventory import Inventory, Project
from .providers import ProviderConfig, ProviderKind

class ProjectSyncError(RuntimeError):
    pass

def _project_path(kind: ProviderKind, organization_uuid: str | None) -> str:
    if kind == ProviderKind.PUBLIC_V2:
        return "/openapi/v2.0/project"
    if kind == ProviderKind.ONPREM_V2:
        if not organization_uuid:
            raise ValueError("On-Premises requires organization UUID")
        try:
            normalized = str(UUID(organization_uuid))
        except (ValueError, AttributeError) as exc:
            raise ValueError("Invalid organization UUID") from exc
        return f"/openapi/v2.0/manage/api/v1/organizations/{normalized}/projects"
    raise ValueError("Project listing requires FlightHub V2")

def parse_projects(kind: ProviderKind, payload: dict) -> tuple[Project, ...]:
    if not isinstance(payload, dict) or payload.get("code") != 0:
        raise ProjectSyncError("Unsuccessful FlightHub response")
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("list"), list):
        raise ProjectSyncError("Invalid FlightHub project list")
    projects = []
    for entry in data["list"]:
        if not isinstance(entry, dict):
            raise ProjectSyncError("Invalid project entry")
        project_id, name = entry.get("uuid"), entry.get("name")
        if not isinstance(project_id, str) or not isinstance(name, str):
            raise ProjectSyncError("Missing project UUID or name")
        try:
            projects.append(Project(kind, project_id, name))
        except ValueError as exc:
            raise ProjectSyncError("Invalid project identity") from exc
    return tuple(projects)

async def fetch_projects(config: ProviderConfig, organization_uuid: str | None = None,
                         page: int = 1, page_size: int = 20) -> tuple[Project, ...]:
    if not 1 <= page <= 100000 or not 1 <= page_size <= 100:
        raise ValueError("Invalid pagination")
    path = _project_path(config.kind, organization_uuid)
    headers = {"X-User-Token": config.access_token, "X-Language": "en",
               "X-Request-Id": str(uuid4())}
    async with httpx.AsyncClient(base_url=config.base_url, timeout=15,
                                 follow_redirects=False, trust_env=False) as client:
        response = await client.get(path, headers=headers, params={
            "usage": "complete", "sort_column": "create_time",
            "sort_type": "desc", "page": page, "page_size": page_size})
        response.raise_for_status()
        payload = response.json()
    return parse_projects(config.kind, payload)

def register_projects(inventory: Inventory, projects: tuple[Project, ...]) -> int:
    """Add validated projects; conflicting entries raise rather than overwrite."""
    for project in projects:
        inventory.add_project(project)
    return len(projects)
