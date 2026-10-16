"""Optional passwordless dashboard/studio access on one trusted LAN.

The mode is opt-in, HTTPS-only, direct-to-Pi, and restricted to one IPv4
subnet and a fixed Host. Proxy/X-Forwarded-For headers are NEVER trusted.
All web browsers on the local subnet can see device data and edit local
studio files while the mode is on; DJI operations remain read-only.
"""
import ipaddress
import os
from urllib.parse import urlsplit

from fastapi import HTTPException, Request


HOME_SUBNET = ipaddress.ip_network("192.168.178.0/24")
ALLOWED_FETCH_SITES = frozenset(("same-origin", "none", ""))


def lan_mode_enabled() -> bool:
    return os.environ.get("AERONEXUS_LAN_NO_TOKEN") == "1"


def require_lan(request: Request) -> None:
    """Fail closed unless HTTPS direct access matches this Pi's LAN address."""
    host = os.environ.get("AERONEXUS_LAN_HOST", "").strip()
    if not host or host != "192.168.178.63":
        raise HTTPException(status_code=503, detail="LAN mode host is not configured")
    try:
        peer = ipaddress.ip_address(request.client.host if request.client else "")
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Only direct LAN clients allowed") from exc
    # Loopback is useful for local health checks and CLI use, never for proxies.
    if not (peer in HOME_SUBNET or peer.is_loopback):
        raise HTTPException(status_code=403, detail="Only direct LAN clients allowed")
    hostname = request.url.hostname
    if hostname not in {host, "localhost", "127.0.0.1"}:
        raise HTTPException(status_code=403, detail="Unexpected request host")
    # WSS is the TLS-equivalent of HTTPS for same-origin WebSocket clients.
    is_socket = request.scope.get("type") == "websocket"
    scheme = "https" if is_socket and request.url.scheme == "wss" else request.url.scheme
    if scheme != "https" and not peer.is_loopback:
        raise HTTPException(status_code=403, detail="LAN access requires HTTPS")
    fetch_site = request.headers.get("sec-fetch-site", "")
    if fetch_site not in ALLOWED_FETCH_SITES:
        raise HTTPException(status_code=403, detail="Cross-site request denied")
    origin = request.headers.get("origin")
    if is_socket and not origin:
        raise HTTPException(status_code=403, detail="WebSocket Origin required")
    if origin:
        try:
            parsed = urlsplit(origin)
            accepted = (
                parsed.scheme == scheme
                and parsed.hostname == hostname
                and parsed.port == request.url.port
                and not parsed.username and not parsed.password
                and parsed.path == "" and parsed.query == ""
                and parsed.fragment == ""
            )
        except ValueError:
            accepted = False
        if not accepted:
            raise HTTPException(status_code=403, detail="Cross-origin request denied")
    # A JavaScript or malicious HTML page on another origin cannot mutate data
    # through form posts (without a matching Origin) or forged cross-site fetch.
    if not is_socket and request.method not in ("GET", "HEAD", "OPTIONS") and not origin:
        # Chrome same-origin fetch for mutations normally sends Sec-Fetch-Site.
        if fetch_site != "same-origin":
            raise HTTPException(status_code=403, detail="Same-origin write required")
    # Explicitly reject any proxy-forwarded chain: client peer is authoritative.
    if any(k in request.headers for k in ("x-forwarded-for", "forwarded", "x-real-ip")):
        raise HTTPException(status_code=403, detail="Proxied access not supported in LAN mode")
