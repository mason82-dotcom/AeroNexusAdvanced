"""Strict read-only transport for explicitly approved DJI API paths.

No default endpoint is assumed. Callers must supply an allowlisted path.

Error classes and retry policy follow alecad/dji-flighthub2-cli (Apache-2.0),
which validated them against the live FlightHub 2 gateway: most domain
failures arrive as HTTP 200 with a non-zero envelope ``code``; transient
gateway statuses are retried with backoff, honouring Retry-After. Errors
carry the X-Request-Id (DJI support asks for it) but never response bodies,
URLs with credentials, or tokens.
"""
import asyncio
from collections.abc import Mapping
import random
from uuid import UUID, uuid4

import httpx

from .providers import API_VERSIONS, ProviderConfig, ProviderKind


USER_AGENT = "aeronexusadvanced/0.1 (read-only)"
RETRY_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})
MAX_RETRIES = 2
_PREFIXES = tuple(f"/openapi/{version}/" for version in API_VERSIONS)


class ReadOnlyTransportError(RuntimeError):
    def __init__(self, message: str, *, request_id: str | None = None,
                 status_code: int | None = None, business_code: int | None = None):
        self.request_id = request_id
        self.status_code = status_code
        self.business_code = business_code
        super().__init__(f"{message} (request_id={request_id})" if request_id else message)


class AuthenticationError(ReadOnlyTransportError):
    """401: organization key missing, invalid, refreshed, or from another region."""


class PermissionDeniedError(ReadOnlyTransportError):
    """403: key valid, but its user lacks permission for the project."""


class NotFoundError(ReadOnlyTransportError):
    """404: unknown route (e.g. not deployed on this gateway) or resource."""


class RateLimitError(ReadOnlyTransportError):
    """429 after retries."""


class ServerError(ReadOnlyTransportError):
    """5xx after retries."""


class BusinessError(ReadOnlyTransportError):
    """HTTP 2xx with a non-zero FlightHub envelope code."""


_AUTH_CODES = frozenset({200401})
_STATUS_ERRORS = {401: AuthenticationError, 403: PermissionDeniedError,
                  404: NotFoundError, 429: RateLimitError}


def _backoff_seconds(attempt: int, retry_after: str | None) -> float:
    if retry_after:
        try:
            return max(0.0, min(float(retry_after), 30.0))
        except ValueError:
            pass
    return min(2 ** attempt * 0.5, 8.0) * (0.5 + random.random())


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
        if (not isinstance(path, str) or not path.startswith(_PREFIXES)
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
        request_id = str(uuid4())
        headers = {"X-User-Token": self._config.access_token, "X-Language": "en",
                   "X-Request-Id": request_id, "Accept": "application/json",
                   "User-Agent": USER_AGENT}
        if project_uuid is not None:
            headers["X-Project-Uuid"] = project_uuid
        try:
            async with httpx.AsyncClient(
                base_url=self._config.base_url, timeout=15,
                follow_redirects=False, trust_env=False
            ) as client:
                for attempt in range(MAX_RETRIES + 1):
                    response = await client.get(path, headers=headers, params=params)
                    if response.status_code not in RETRY_STATUSES or attempt == MAX_RETRIES:
                        break
                    await asyncio.sleep(_backoff_seconds(
                        attempt, response.headers.get("Retry-After")))
                status = response.status_code
                if status >= 400:
                    cls = _STATUS_ERRORS.get(status, ServerError if status >= 500
                                             else ReadOnlyTransportError)
                    raise cls(f"DJI read-only request failed: HTTP {status}",
                              request_id=request_id, status_code=status)
                if not 200 <= status < 300:
                    raise ReadOnlyTransportError(f"Unexpected HTTP {status}",
                                                 request_id=request_id, status_code=status)
                payload = response.json()
        except ReadOnlyTransportError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise ReadOnlyTransportError("DJI read-only request failed",
                                         request_id=request_id) from exc
        if not isinstance(payload, dict) or type(payload.get("code")) is not int:
            raise ReadOnlyTransportError("DJI response rejected", request_id=request_id)
        if payload["code"] != 0:
            # The Public Cloud gateway answers a missing/invalid key with HTTP 200
            # and code 200401 (observed on es-flight-api-eu/us, 2026-10-16).
            cls = AuthenticationError if payload["code"] in _AUTH_CODES else BusinessError
            raise cls("DJI business error", request_id=request_id,
                      business_code=payload["code"])
        return payload
