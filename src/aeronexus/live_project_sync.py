"""Documented FlightHub V2 project GET via the strict read-only transport."""
from uuid import UUID
from .inventory import Inventory
from .project_sync import parse_projects
from .providers import ProviderConfig, ProviderKind
from .read_only_transport import ReadOnlyTransport

def project_list_path(kind: ProviderKind, organization_uuid: str | None = None) -> str:
    if kind == ProviderKind.PUBLIC_V2:
        return "/openapi/v2.0/project"
    if kind == ProviderKind.ONPREM_V2:
        if not isinstance(organization_uuid, str):
            raise ValueError("Organization UUID required")
        try:
            normalized = str(UUID(organization_uuid))
        except ValueError as exc:
            raise ValueError("Invalid organization UUID") from exc
        return f"/openapi/v2.0/manage/api/v1/organizations/{normalized}/projects"
    raise ValueError("Unsupported provider")

async def read_project_page(config: ProviderConfig, *, organization_uuid: str | None = None,
                            page: int = 1, page_size: int = 20):
    """Read one documented project page; never modifies remote state."""
    if type(page) is not int or type(page_size) is not int or not (1 <= page <= 100000 and 1 <= page_size <= 100):
        raise ValueError("Invalid pagination")
    path = (config.path("/project") if config.kind == ProviderKind.PUBLIC_V2
            else project_list_path(config.kind, organization_uuid))
    transport = ReadOnlyTransport(config, frozenset({path}))
    payload = await transport.get(path, {
        "usage": "complete", "sort_column": "create_time",
        "sort_type": "desc", "page": page, "page_size": page_size})
    return parse_projects(config.kind, payload)

async def sync_project_page(inventory: Inventory, config: ProviderConfig, *,
                            organization_uuid: str | None = None,
                            page: int = 1, page_size: int = 20) -> int:
    """Stage project identities before committing to inventory."""
    if not isinstance(inventory, Inventory):
        raise TypeError("Inventory required")
    projects = await read_project_page(config, organization_uuid=organization_uuid,
                                       page=page, page_size=page_size)
    seen = set()
    for project in projects:
        key = (project.provider, project.project_id)
        if key in seen:
            raise ValueError("Duplicate project in response")
        seen.add(key)
        existing = inventory._projects.get(key)
        if existing is not None and existing != project:
            raise ValueError("Conflicting project identity")
    for project in projects:
        inventory.add_project(project)
    return len(projects)
