"""FlightHub standalone component ideas mapped to safe local Operations Center.

The DJI upstream examples use proprietary paas.js, project tokens and a
dedicated backend. Our page deliberately uses only existing AeroNexus APIs.
"""
from html.parser import HTMLParser

from fastapi.testclient import TestClient

from aeronexus.app import app
from aeronexus.operations_page import render_operations


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_quad_area_contains_project_map_cockpit_waylines_and_flight_tracks():
    page = render_operations()
    tags = Tags()
    tags.feed(page)
    ids = {attrs["id"] for _, attrs in tags.tags if "id" in attrs}
    for item in (
        "project-panel", "project-filter", "project-devices",
        "operations-map", "tile-choice", "map-forst",
        "cockpit-select", "cockpit-content", "cockpit-freshness",
        "catalog-items", "flight-tracks", "saved-missions",
        "map-message", "project-sync", "refresh-now",
    ):
        assert item in ids


def test_leaflet_css_and_js_exact_official_1_9_4_sri():
    page = render_operations()
    parser = Tags()
    parser.feed(page)
    styles = [
        a for tag, a in parser.tags
        if tag == "link" and a.get("rel") == "stylesheet"
    ]
    scripts = [
        a for tag, a in parser.tags
        if tag == "script" and "src" in a
    ]
    assert len(styles) == len(scripts) == 1
    assert styles[0]["href"].endswith("leaflet@1.9.4/dist/leaflet.css")
    assert styles[0]["integrity"] == (
        "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
    )
    assert scripts[0]["integrity"] == (
        "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
    )


def test_forst_and_no_dji_remote_host_are_used():
    page = render_operations()
    assert "49.1533,lon:8.58417,zoom:15" in page
    assert "id=\"map-forst\"" in page
    assert "mapLayers.satellite.addTo(map)" in page
    assert "tile.openstreetmap.org" in page
    assert "referrerPolicy:\"strict-origin-when-cross-origin\"" in page
    assert "djigate.com" not in page
    assert "paas.js" not in page
    assert ":30812" not in page
    assert "projectToken" not in page
    assert "WebSocket" not in page
    assert "Authorization" not in page


def test_operations_cockpit_only_shows_fresh_device_position():
    page = render_operations()
    assert 'd.freshness!=="fresh"||d.online!==true' in page
    assert "(t.latitude===0&&t.longitude===0)" in page
    assert "circleMarker(loc" in page
    assert "renderCockpit()" in page
    assert "health" in page
    assert "Cockpit" in page
    assert "Standby" in page
    assert "Akku (letzter Messwert)" in page
    assert "HMS" in page


def test_library_and_tracks_are_read_only_and_scoped_to_cached_tasks():
    page = render_operations()
    assert 'getJSON("/api/v1/flighthub/catalog")' in page
    assert 'getJSON("/api/v1/status/devices?limit=200")' in page
    assert 'getJSON("/api/v1/studio/missions")' in page
    assert 'getJSON("/api/v1/status/summary")' in page
    assert '/api/v1/flighthub/projects/' in page
    assert '/tasks/' in page and '/track' in page
    assert '/api/v1/studio/missions/' in page
    assert "mission.close_route&&coords.length>=3" in page
    assert "feature?.geometry?.type!==\"LineString\"" in page
    assert "Promise.allSettled" in page
    assert "window.setInterval(refreshAll,15000)" in page
    assert "fetch(path,{cache:\"no-store\"})" in page
    assert 'method:"POST"' not in page
    assert "innerHTML" not in page
    assert "localStorage" not in page
    assert "URLSearchParams" not in page


def test_dynamic_names_are_never_interpreted_as_html():
    page = render_operations()
    assert "el.textContent=String(text)" in page
    assert 'dot.bindTooltip(elem("span","",(d.name||"Fluggerät")+" · aktuell"))' in page
    assert "document.createElement(tag)" in page


def test_static_html_has_no_live_identifiers_or_secrets(monkeypatch):
    token = "test-token-012345678901234567890123456789"
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", token)
    with TestClient(app) as client:
        res = client.get("/operations")
        assert res.status_code == 200
        assert "Operations Center" in res.text
        assert token not in res.text
        assert res.headers["cache-control"] == "no-store"
        assert res.headers["x-frame-options"] == "DENY"
        assert "frame-ancestors 'none'" in res.headers["content-security-policy"]
        assert "https://cdn.jsdelivr.net" in res.headers["content-security-policy"]
        assert client.post("/api/v1/flight/command").status_code == 403
