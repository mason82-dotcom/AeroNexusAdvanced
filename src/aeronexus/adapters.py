"""Transport foundation; no DJI endpoint paths are guessed."""
from dataclasses import dataclass
from urllib.parse import urlparse
import httpx

@dataclass(frozen=True)
class DJIAdapter:
    base_url: str
    token: str

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("DJI base URL must be an HTTPS origin without credentials")

    async def get(self, path: str, project_uuid: str | None = None) -> dict:
        if not path.startswith("/") or path.startswith("//") or "://" in path:
            raise ValueError("Expected an absolute API path")
        headers = {"X-User-Token": self.token}
        if project_uuid:
            headers["X-Project-Uuid"] = project_uuid
        async with httpx.AsyncClient(base_url=self.base_url, timeout=15, follow_redirects=False) as client:
            response = await client.get(path, headers=headers)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and data.get("code") not in (None, 0):
                raise ValueError("DJI business API returned an error")
            return data
