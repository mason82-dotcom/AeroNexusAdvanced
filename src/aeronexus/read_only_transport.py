"""Strict read-only transport for explicitly approved DJI API paths.

No default endpoint is assumed. Callers must supply an allowlisted path.
"""
from collections.abc import Mapping
from uuid import UUID, uuid4
import httpx
from .providers import ProviderConfig, ProviderKind

class ReadOnlyTransportError(RuntimeError):
    pass

class ReadOnlyTransport:
    def __init__(self, config: ProviderConfig, allowed_paths: frozenset[str]):
        if not isinstance(config, ProviderConfig):
            raise TypeError("ProviderConfig required")
        if config.kind not in (ProviderKind.PUBLIC_V2, ProviderKind.ONPREM_V2):
            raise ValueError("Only FlightHub V2 is supported by this transport")
        if not isinstance(allowed_paths, frozenset) or not allowed_paths:
            raise ValueError("Explicit nonempty path allowlist required")
        for path in allowed_paths:
            self._validate_path(path)
        self._config = config
        self._allowed_paths = allowed_paths

    @staticmethod
    def _validate_path(path: str) -> None:
        if (not isinstance(path, str) or not path.startswith("/openapi/v2.0/")
                or path.startswith("//") or "?" in path or "#" in path
                or "\\" in path or "%" in path
                or any(part in ("", ".", "..") for part in path.split("/")[1:])):
            raise ValueError("Unsafe API path")

    async def get(self, path: str, params: Mapping[str, str | int] | None = None,
                  *, project_uuid: str | None = None) -> dict:
        self._validate_path(path)
        if path not in self._allowed_paths:
            raise ReadOnlyTransportError("API path not approved")
        if params is not None:
            if not isinstance(params, Mapping) or any(
                not isinstance(k, str) or not k or
                type(v) not in (str, int) for k, v in params.items()
            ):
                raise ValueError("Invalid query parameters")
        if project_uuid is not None:
            if not isinstance(project_uuid, str):
                raise ValueError("Invalid project UUID")
            try:
                project_uuid = str(UUID(project_uuid))
            except ValueError as exc:
                raise ValueError("Invalid project UUID") from exc
        headers = {"X-User-Token": self._config.access_token,
                   "X-Language": "en", "X-Request-Id": str(uuid4())}
        if project_uuid is not None:
            headers["X-Project-Uuid"] = project_uuid
        try:
            async with httpx.AsyncClient(
                base_url=self._config.base_url, timeout=15,
                follow_redirects=False, trust_env=False
            ) as client:
                response = await client.get(path, headers=headers, params=params)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ReadOnlyTransportError("DJI read-only request failed") from exc
        if not isinstance(payload, dict) or type(payload.get("code")) is not int or payload["code"] != 0:
            raise ReadOnlyTransportError("DJI response rejected")
        return payload
