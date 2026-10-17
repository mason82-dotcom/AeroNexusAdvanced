"""Livestream relay: MediaMTX path list, WHEP signalling, safety limits, API."""
import importlib
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from aeronexus.livestream import (LiveError, LiveNotFound, LiveSettings, LiveStreams,
                                  LiveUnavailable, dji_stream, stream_id)

APP_MODULE = importlib.import_module("aeronexus.app")
TOKEN = "livestream-test-only-dashboard-token-123456"
HEADERS = {"Authorization": "Bearer " + TOKEN}
SN = "1581F8HGX000TEST"
PATH = f"live/{SN}-99-0-0"
SESSION = "0b1c2d3e-4f50-4a6b-8c7d-9e0f1a2b3c4d"
OFFER = b"v=0\r\no=- 1 1 IN IP4 0.0.0.0\r\ns=-\r\nm=video 9 UDP/TLS/RTP/SAVPF 96\r\n"
ANSWER = b"v=0\r\no=- 2 2 IN IP4 192.168.178.63\r\ns=-\r\nm=video 9 UDP/TLS/RTP/SAVPF 96\r\n"


class FakeMediaMtx:
    def __init__(self, *, ready=True, tracks=("H264",), whep_status=201, error=""):
        self.ready, self.tracks, self.whep_status, self.error = ready, list(tracks), whep_status, error
        self.calls = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, request.url.host, request.url.port, request.url.path))
        if request.url.path == "/v3/paths/list":
            return httpx.Response(200, json={"items": [
                {"name": PATH, "ready": self.ready, "readyTime": "2026-10-17T12:00:00Z",
                 "tracks": self.tracks, "source": {"type": "rtmpConn"}, "readers": [],
                 "bytesReceived": 1234},
                {"name": "../etc/passwd", "ready": True, "tracks": ["H264"]},
                {"name": "other/cam", "ready": False, "tracks": []}]})
        if request.method == "POST" and request.url.path == f"/{PATH}/whep":
            assert request.headers["content-type"] == "application/sdp"
            if self.whep_status != 201:
                return httpx.Response(self.whep_status, json={"status": "error", "error": self.error})
            return httpx.Response(201, content=ANSWER, headers={
                "Content-Type": "application/sdp", "Location": f"/{PATH}/whep/{SESSION}"})
        if request.method == "DELETE" and request.url.path == f"/{PATH}/whep/{SESSION}":
            return httpx.Response(200)
        return httpx.Response(404)


def live(fake):
    return LiveStreams(LiveSettings(), transport=httpx.MockTransport(fake))


def test_settings_only_accept_loopback_http():
    assert LiveSettings.from_env({}).api_url == "http://127.0.0.1:9997"
    assert LiveSettings.from_env({"AERONEXUS_MEDIAMTX_API": "http://localhost:9997/"}).api_url \
        == "http://localhost:9997"
    for bad in ("http://192.168.178.63:9997", "https://127.0.0.1:9997", "http://u:p@127.0.0.1:1",
                "http://127.0.0.1:9997/v3", "http://evil.example", "file:///etc"):
        with pytest.raises(ValueError):
            LiveSettings.from_env({"AERONEXUS_MEDIAMTX_WEBRTC": bad})


def test_stream_paths_and_ids():
    assert dji_stream(PATH) == (SN, "99-0-0")
    assert dji_stream("live/abc-1") is None and dji_stream(PATH + "/x") is None
    assert len(stream_id(PATH)) == 24 and stream_id(PATH) != stream_id("live/other")


def test_streams_hide_paths_and_serials_and_skip_invalid():
    fake = FakeMediaMtx()
    streams = live(fake).streams({SN: "Matrice 4T"})
    assert [s["label"] for s in streams] == ["Matrice 4T · Nutzlast 99-0-0"]
    assert streams[0]["id"] == stream_id(PATH) and streams[0]["browser_playable"]
    assert SN not in json.dumps(streams) and "live/" not in json.dumps(streams)
    assert live(fake).streams()[0]["label"] == "DJI-Fluggerät · Nutzlast 99-0-0"
    assert not live(FakeMediaMtx(tracks=["H265"])).streams()[0]["browser_playable"]
    assert {(h, p) for _, h, p, _ in fake.calls} == {("127.0.0.1", 9997)}


def test_offer_relays_sdp_and_returns_session():
    fake = FakeMediaMtx()
    answer, session = live(fake).offer(stream_id(PATH), OFFER)
    assert answer.encode() == ANSWER and session == SESSION
    assert ("POST", "127.0.0.1", 8889, f"/{PATH}/whep") in fake.calls
    live(fake).close(stream_id(PATH), SESSION)
    assert fake.calls[-1][0] == "DELETE"


def test_offer_validation_and_error_mapping():
    with pytest.raises(LiveError):
        live(FakeMediaMtx()).offer(stream_id(PATH), b"not sdp")
    with pytest.raises(LiveError):
        live(FakeMediaMtx()).offer(stream_id(PATH), OFFER + b"a" * 70000)
    with pytest.raises(LiveNotFound):
        live(FakeMediaMtx()).offer("f" * 24, OFFER)
    with pytest.raises(LiveNotFound):
        live(FakeMediaMtx()).offer("../../v3", OFFER)
    with pytest.raises(LiveNotFound):
        live(FakeMediaMtx(ready=False)).offer(stream_id(PATH), OFFER)
    with pytest.raises(LiveError, match="H.264"):
        live(FakeMediaMtx(whep_status=400, error="codecs not supported by client")).offer(
            stream_id(PATH), OFFER)
    with pytest.raises(LiveNotFound):
        live(FakeMediaMtx()).close(stream_id(PATH), "not-a-session")

    def down(request):
        raise httpx.ConnectError("refused")
    with pytest.raises(LiveUnavailable):
        live(down).streams()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    fake = FakeMediaMtx()
    monkeypatch.setattr(APP_MODULE, "LiveStreams", lambda: live(fake))
    return TestClient(APP_MODULE.app)


def test_api_list_offer_close_and_access(client):
    sid = stream_id(PATH)
    assert client.get("/api/v1/live/streams").status_code == 401
    data = client.get("/api/v1/live/streams", headers=HEADERS).json()
    assert data["available"] and data["streams"][0]["id"] == sid
    r = client.post(f"/api/v1/live/streams/{sid}/whep", content=OFFER,
                    headers={**HEADERS, "Content-Type": "application/sdp"})
    assert r.status_code == 201 and r.content == ANSWER
    assert r.headers["x-live-session"] == SESSION and r.headers["content-type"].startswith("application/sdp")
    # text/plain is CORS-safelisted (cross-site form posts): rejected
    assert client.post(f"/api/v1/live/streams/{sid}/whep", content=OFFER,
                       headers={**HEADERS, "Content-Type": "text/plain"}).status_code == 415
    assert client.post(f"/api/v1/live/streams/{sid}/whep", content=OFFER,
                       headers={"Content-Type": "application/sdp"}).status_code == 401
    assert client.delete(f"/api/v1/live/streams/{sid}/whep/{SESSION}", headers=HEADERS).status_code == 204


def test_api_reports_unavailable_server(client, monkeypatch):
    def down(request):
        raise httpx.ConnectError("refused")
    monkeypatch.setattr(APP_MODULE, "LiveStreams", lambda: live(down))
    assert client.get("/api/v1/live/streams", headers=HEADERS).json() == {"available": False, "streams": []}
    r = client.post(f"/api/v1/live/streams/{stream_id(PATH)}/whep", content=OFFER,
                    headers={**HEADERS, "Content-Type": "application/sdp"})
    assert r.status_code == 503


def test_operations_page_has_live_panel(client):
    from aeronexus.operations_page import HTML
    assert 'id="live-panel"' in HTML and "/api/v1/live/streams" in HTML
    assert "8889" not in HTML and "rtmp://" not in HTML  # no direct MediaMTX URLs in the page
