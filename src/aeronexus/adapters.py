"""Strict HTTPS read-only transport; provider authentication is configured separately."""
from dataclasses import dataclass
from urllib.parse import urlsplit
import httpx

@dataclass(frozen=True)
class DJIAdapter:
    base_url: str
    token: str

    def __post_init__(self) -> None:
        parsed = urlsplit(self.base_url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
            raise ValueError("DJI base URL must be an HTTPS origin without credentials or path")

    async def get(self, path: str, project_uuid: str | None = None) -> dict:
        parsed = urlsplit(path)
        if (not path.startswith("/") or path.startswith("//") or parsed.scheme or parsed.netloc
                or parsed.fragment or "\\" in path or any(part in (".", "..") for part in parsed.path.split("/"))):
            raise ValueError("Expected a safe absolute API path")
        headers = {"X-User-Token": self.token}
        if project_uuid:
            headers["X-Project-Uuid"] = project_uuid
        async with httpx.AsyncClient(base_url=self.base_url, timeout=15, follow_redirects=False,
                                     trust_env=False) as client:
            response = await client.get(path, headers=headers)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object")
            if data.get("code") not in (None, 0):
                raise ValueError("DJI business API returned an error")
            return data
