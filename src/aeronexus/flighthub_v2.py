"""Documented FlightHub 2 OpenAPI V2 read-only requests.

Requires an externally obtained user token. No login or flight-control actions.
"""
from dataclasses import dataclass
from enum import StrEnum
from uuid import uuid4
import httpx
from .providers import ProviderConfig, ProviderKind

class FlightHubError(RuntimeError):
    pass

@dataclass(frozen=True)
class FlightHubV2:
    config: ProviderConfig

    def __post_init__(self):
        if self.config.kind not in (ProviderKind.PUBLIC_V2, ProviderKind.ONPREM_V2):
            raise ValueError("FlightHubV2 requires a FlightHub provider")

    async def _get(self, path: str, project_uuid: str | None = None) -> dict:
        if not path.startswith("/openapi/v2.0/") or "?" in path or "#" in path:
            raise ValueError("Unexpected FlightHub V2 path")
        headers = {
            "X-User-Token": self.config.access_token,
            "X-Language": "en",
            "X-Request-Id": str(uuid4()),
        }
        if project_uuid:
            headers["X-Project-Uuid"] = project_uuid
        async with httpx.AsyncClient(base_url=self.config.base_url, timeout=15,
                                     follow_redirects=False, trust_env=False) as client:
            response = await client.get(path, headers=headers)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict) or payload.get("code") != 0:
            raise FlightHubError("FlightHub V2 returned an unsuccessful response")
        return payload

    async def system_status(self) -> dict:
        if self.config.kind is not ProviderKind.PUBLIC_V2:
            raise ValueError("Public Cloud only")
        return await self._get("/openapi/v2.0/system_status")

    async def realtime_control_health(self, project_uuid: str) -> dict:
        if self.config.kind is not ProviderKind.ONPREM_V2:
            raise ValueError("On-Premises only")
        if not project_uuid or "/" in project_uuid:
            raise ValueError("Invalid project UUID")
        return await self._get("/openapi/v2.0/drc/health", project_uuid=project_uuid)
