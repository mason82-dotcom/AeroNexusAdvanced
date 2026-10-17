"""Livestream relay for the Operations Center (local DJI Cloud API stack).

DJI Pilot 2 publishes the aircraft camera via RTMP/WHIP to MediaMTX (see
deploy/cloud-server/mediamtx.yml). The Operations Center is served via HTTPS,
MediaMTX via plain HTTP on the LAN, so a browser would block direct requests as
mixed content. This module relays only the WebRTC signalling (WHEP offer and
answer, session teardown); the media then flows over DTLS-SRTP/UDP directly
between MediaMTX and the browser.

Safety:
* MediaMTX endpoints must be loopback HTTP URLs (no configurable SSRF target).
* The browser never sees stream paths: those contain the aircraft serial.
  Streams are addressed by an opaque id derived from the path and resolved
  against the current MediaMTX path list on every request.
* Bounded SDP sizes, short timeouts, no redirects, no proxy settings from the
  environment. Upstream error texts are mapped, never echoed.
* Nothing is sent to the aircraft; watching never changes DJI state.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import ipaddress
import os
import re
from urllib.parse import quote, urlsplit

import httpx

DEFAULT_API = "http://127.0.0.1:9997"
DEFAULT_WEBRTC = "http://127.0.0.1:8889"
MAX_SDP_BYTES = 64 * 1024
TIMEOUT = httpx.Timeout(5.0, connect=2.0)
_PATH_RE = re.compile(r"[A-Za-z0-9_.-]{1,64}(/[A-Za-z0-9_.-]{1,64}){0,3}\Z")
# Backend (LiveStreamServiceImpl): live/<droneSn>-<PayloadIndex type-subtype-position>
_DJI_PATH_RE = re.compile(r"live/([A-Z0-9]{8,32})-(\d{1,5}-\d{1,3}-\d{1,3})\Z")
_SESSION_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
_STREAM_ID_RE = re.compile(r"[0-9a-f]{24}\Z")
BROWSER_CODECS = {"H264", "VP8", "VP9", "AV1"}


class LiveError(ValueError):
    """Invalid request (bad SDP, unsupported codec)."""


class LiveNotFound(LiveError):
    pass


class LiveUnavailable(RuntimeError):
    """MediaMTX not running or not reachable."""


def _loopback_url(value: str, name: str) -> str:
    parts = urlsplit(value.strip())
    host = parts.hostname or ""
    try:
        loopback = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = False
    if (parts.scheme != "http" or not loopback or parts.username or parts.password
            or parts.path not in ("", "/") or parts.query or parts.fragment):
        raise ValueError(f"{name} must be a plain http://127.0.0.1:<port> URL")
    return f"http://{parts.netloc}"


@dataclass(frozen=True)
class LiveSettings:
    api_url: str = DEFAULT_API
    webrtc_url: str = DEFAULT_WEBRTC

    @classmethod
    def from_env(cls, environ=None) -> "LiveSettings":
        env = os.environ if environ is None else environ
        return cls(_loopback_url(env.get("AERONEXUS_MEDIAMTX_API", DEFAULT_API),
                                 "AERONEXUS_MEDIAMTX_API"),
                   _loopback_url(env.get("AERONEXUS_MEDIAMTX_WEBRTC", DEFAULT_WEBRTC),
                                 "AERONEXUS_MEDIAMTX_WEBRTC"))


def stream_id(path: str) -> str:
    return hashlib.sha256(("aeronexus-live\0" + path).encode()).hexdigest()[:24]


def dji_stream(path: str) -> tuple[str, str] | None:
    """(serial, payload index "type-subtype-position") of a backend stream path."""
    match = _DJI_PATH_RE.fullmatch(path)
    return (match.group(1), match.group(2)) if match else None


def _validate_sdp(sdp: bytes) -> str:
    if not sdp or len(sdp) > MAX_SDP_BYTES:
        raise LiveError("SDP fehlt oder ist zu groß")
    try:
        text = sdp.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LiveError("SDP ist kein UTF-8") from exc
    if not text.startswith("v=0") or "m=video" not in text:
        raise LiveError("Kein gültiges WebRTC-Angebot (SDP)")
    return text


class LiveStreams:
    def __init__(self, settings: LiveSettings | None = None, *, transport=None):
        self.settings = settings or LiveSettings.from_env()
        self._transport = transport

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=TIMEOUT, follow_redirects=False, trust_env=False,
                            transport=self._transport)

    def _paths(self) -> list[dict]:
        try:
            with self._client() as client:
                response = client.get(self.settings.api_url + "/v3/paths/list",
                                      params={"itemsPerPage": 100})
        except httpx.HTTPError as exc:
            raise LiveUnavailable("MediaMTX nicht erreichbar") from exc
        if response.status_code != 200:
            raise LiveUnavailable("MediaMTX-API antwortet nicht wie erwartet")
        try:
            items = response.json().get("items") or []
        except ValueError as exc:
            raise LiveUnavailable("MediaMTX-API liefert kein JSON") from exc
        return [i for i in items if isinstance(i, dict) and isinstance(i.get("name"), str)
                and _PATH_RE.fullmatch(i["name"]) and ".." not in i["name"]]

    def streams(self, device_names: dict[str, str] | None = None) -> list[dict]:
        """Active (ready) streams; labels from known device names, never serials."""
        names = device_names or {}
        out = []
        for item in self._paths():
            if not item.get("ready"):
                continue
            path = item["name"]
            tracks = [t for t in (item.get("tracks") or []) if isinstance(t, str)][:8]
            dji = dji_stream(path)
            if dji:
                device = names.get(dji[0]) or "DJI-Fluggerät"
                label = f"{device} · Nutzlast {dji[1]}"
            else:
                label = "Stream " + stream_id(path)[:6]
            readers = item.get("readers")
            source = item.get("source") if isinstance(item.get("source"), dict) else {}
            out.append({
                "id": stream_id(path), "label": label, "dji": bool(dji),
                "payload": dji[1] if dji else None,
                "tracks": tracks,
                "browser_playable": any(t.upper() in BROWSER_CODECS for t in tracks),
                "source": source.get("type") if isinstance(source.get("type"), str) else None,
                "ready_since": item.get("readyTime") if isinstance(item.get("readyTime"), str) else None,
                "viewers": len(readers) if isinstance(readers, list) else None,
                "bytes_received": item.get("bytesReceived")
                if isinstance(item.get("bytesReceived"), int) else None,
            })
        return sorted(out, key=lambda s: s["label"])

    def _path_for(self, sid: str) -> str:
        if not _STREAM_ID_RE.fullmatch(sid):
            raise LiveNotFound("Unbekannter Stream")
        for item in self._paths():
            if item.get("ready") and stream_id(item["name"]) == sid:
                return item["name"]
        raise LiveNotFound("Stream nicht (mehr) aktiv")

    def _whep_url(self, path: str) -> str:
        return f"{self.settings.webrtc_url}/{quote(path, safe='/')}/whep"

    def offer(self, sid: str, sdp: bytes) -> tuple[str, str]:
        """Forward a complete (non-trickle) WHEP offer; returns (answer, session)."""
        text = _validate_sdp(sdp)
        path = self._path_for(sid)
        try:
            with self._client() as client:
                response = client.post(self._whep_url(path), content=text.encode(),
                                       headers={"Content-Type": "application/sdp"})
        except httpx.HTTPError as exc:
            raise LiveUnavailable("MediaMTX nicht erreichbar") from exc
        if response.status_code == 404:
            raise LiveNotFound("Stream nicht (mehr) aktiv")
        if response.status_code in (400, 406):
            try:
                detail = str(response.json().get("error", ""))
            except ValueError:
                detail = ""
            if "codec" in detail.lower():
                raise LiveError("Der Browser unterstützt den Videocodec nicht "
                                "(in DJI Pilot 2 H.264 wählen)")
            raise LiveError("WebRTC-Angebot abgelehnt")
        if response.status_code != 201:
            raise LiveUnavailable("MediaMTX hat die Wiedergabe nicht gestartet")
        answer = response.content
        if not answer or len(answer) > MAX_SDP_BYTES or not answer.startswith(b"v=0"):
            raise LiveUnavailable("Ungültige WebRTC-Antwort von MediaMTX")
        session = response.headers.get("Location", "").rstrip("/").rsplit("/", 1)[-1]
        if not _SESSION_RE.fullmatch(session):
            raise LiveUnavailable("MediaMTX lieferte keine Sitzungskennung")
        return answer.decode("utf-8"), session

    def close(self, sid: str, session: str) -> None:
        if not _SESSION_RE.fullmatch(session):
            raise LiveNotFound("Unbekannte Sitzung")
        try:
            path = self._path_for(sid)
        except LiveNotFound:
            return  # stream ended: MediaMTX already dropped the session
        try:
            with self._client() as client:
                client.delete(self._whep_url(path) + "/" + session)
        except httpx.HTTPError as exc:
            raise LiveUnavailable("MediaMTX nicht erreichbar") from exc
