"""Explicitly enabled LAN session handoff from the existing local Cloud UI."""
import asyncio
import ipaddress
import time

from fastapi import HTTPException, Request
import httpx

from .lan_access import home_subnet, lan_host, lan_mode_enabled
from .local_waylines import (ORIGIN, Credentials, LocalWaylineError, _json_response,
                             credentials_path, load_credentials, save_credentials, handoff_enabled)


def handoff_origin(request: Request) -> str:
    """Dedicated exact-origin policy; existing viewer authorization is unchanged."""
    host = lan_host()
    origin = request.headers.get("origin", "")
    try:
        peer = ipaddress.ip_address(request.client.host)
    except (ValueError, AttributeError):
        raise HTTPException(403, "Local Cloud session origin required") from None
    if (not lan_mode_enabled() or host is None or request.url.scheme != "https"
            or request.url.hostname != host
            or request.url.port != 8000
            or not (peer in (home_subnet() or ()) or peer.is_loopback)
            or origin != f"http://{host}:8085" or not handoff_enabled()):
        raise HTTPException(403, "Local Cloud session origin required")
    return origin


async def verify_session(credentials: Credentials, *, transport=None) -> None:
    async with httpx.AsyncClient(base_url=ORIGIN, timeout=5, trust_env=False,
                                 follow_redirects=False, transport=transport) as client:
        async with client.stream("GET", "/manage/api/v1/users/current",
                                 headers={"x-auth-token": credentials.access_token}) as response:
            user = await _json_response(response)
    # Never trust a browser-supplied workspace or merely decode an unsigned JWT.
    if (user.get("workspace_id") != credentials.workspace_id
            or type(user.get("user_type")) is not int or user["user_type"] not in (1, 2)):
        raise LocalWaylineError("authentication_required")


class LocalSessionHandoff:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._verified = None
        self._until = 0.0

    async def accept(self, credentials: Credentials) -> None:
        async with self._lock:
            previous = load_credentials(credentials_path())
            if previous and previous.workspace_id != credentials.workspace_id:
                raise LocalWaylineError("workspace_conflict")
            if credentials == previous == self._verified and time.monotonic() < self._until:
                return
            try:
                await asyncio.wait_for(verify_session(credentials), 8)
            except httpx.HTTPError:
                raise LocalWaylineError("session_unavailable") from None
            if previous != credentials:
                save_credentials(credentials_path(), credentials)
            self._verified = credentials
            self._until = time.monotonic() + 60
