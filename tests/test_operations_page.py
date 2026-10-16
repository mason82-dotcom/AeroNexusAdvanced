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
    assert '"Akku"+labelSuffix' in page
    assert 'id="cockpit-summary"' in page
    assert 'id="cockpit-connection"' in page
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


def test_dji_public_task_state_inbox_filters_and_groups_existing_cache():
    page = render_operations()
    assert 'id="tasks-in-progress"' in page
    assert 'id="tasks-finished"' in page
    assert 'id="tasks-all"' in page
    assert 'function taskState(status)' in page
    assert 'waiting:["Ausstehend","pending","progress"]' in page
    assert 'executing:["In Ausführung","active","progress"]' in page
    assert 'success:["Erfolgreich","complete","finished"]' in page
    assert 'partially_done:["Teilweise abgeschlossen","failed","finished"]' in page
    assert 'starting_failure:["Start fehlgeschlagen","failed","finished"]' in page
    assert 'timeout:["Zeitüberschreitung","failed","finished"]' in page
    assert '["Unbekannter Status","pending","unknown"]' in page
    assert 'function taskDate(t)' in page
    assert 'className' in page
    assert 'aria-pressed' in page
    assert 'task.current_waypoint_index' in page
    assert 'task.total_waypoints' in page
    assert 'task.media_upload_status' in page
    assert 'task.exceptions>0' in page


def test_cockpit_uses_only_normalized_drone_metrics():
    page = render_operations()
    assert "Flugzeit gesamt" in page
    assert "Flugstarts gesamt" in page
    assert "Distanz zum Homepoint" in page
    assert "Höhe über Start" in page
    assert "Akkuspannung" in page
    assert "Akkutemperatur" in page
    assert "RTK-Satelliten" in page
    assert "Keine bestätigte Live-Verbindung" in page
    assert "DJI-Code" in page
    assert 'd.kind==="aircraft"' in page


def test_no_dji_task_create_or_microfrontend_runtime():
    page = render_operations()
    for path in (
        "/openapi/v2.0/task/api/v1/workspaces/",
        "/flight-tasks",
        "FH2.initConfig",
        "FH2.loadCockpit",
        "loadWaylineCreation",
        "x-user-token",
        "X-Project-Uuid",
        "paas.js",
    ):
        assert path not in page
    assert "DJI" in page
    assert "nur lesen" in page.lower() or "Nur lesen" in page


def test_flight_task_media_catalog_from_cli_is_metadata_only():
    html = render_operations()
    assert "Medienliste anzeigen" in html
    assert "async function viewTaskMedia(projectId,taskUuid,container)" in html
    assert '/tasks/"+encodeURIComponent(taskUuid)+"/media' in html
    assert "Keine Download- oder Vorschau-URLs freigegeben" in html
    assert "file.size_bytes" in html
    assert "original_url" not in html
    assert "preview_url" not in html


def test_cloud_api2_optional_source_status_and_backend_not_exposed():
    html = render_operations()
    assert 'id="cloud-api-panel"' in html
    assert 'id="cloud-api-state"' in html
    assert 'getJSON("/api/v1/cloudapi2/devices")' in html
    assert '"dji-cloud-api-2"' in html
    assert "Cloud-API-2-Schnittstelle nicht verfügbar" in html
    assert "AERONEXUS_CLOUDAPI2_BFF_TOKEN" not in html
    assert "Bearer " not in html
    assert "SDK-Backend" in html


def test_cockpit_separates_online_status_from_data_age_and_preserves_detail_state():
    page = render_operations()
    assert 'function connectionStatus(device)' in page
    assert 'device.online===true' in page
    assert 'device.online===false' in page
    assert 'function freshnessStatus(device)' in page
    assert 'fresh:"Daten aktuell"' in page
    assert 'stale:"Daten veraltet"' in page
    assert 'unknown_age:"Alter unbekannt"' in page
    assert 'clock_skew:"Zeitabweichung"' in page
    assert 'device.freshness==="fresh"?"good":"warn"' in page
    assert 'd.freshness==="fresh"&&d.online===true' in page
    assert 'id="cockpit-summary"' in page
    assert 'id="cockpit-connection"' in page
    assert 'id="cockpit-received"' in page
    assert 'id="cockpit-content"' in page
    assert 'body.querySelector("#cockpit-technical")?.open===true' in page
    assert 'body.scrollTop=oldScroll' in page
    assert "0 bedeutet nicht zwingend" in page


def test_cockpit_human_rtk_status_and_raw_enum_are_separate():
    page = render_operations()
    assert '"is_fixed:not_started":"RTK nicht gestartet"' in page
    assert '"is_fixed:fixing":"RTK-Fix läuft"' in page
    assert '"is_fixed:fixing_successful":"RTK-Fix erfolgreich"' in page
    assert '"is_fixed:fixing_failed":"RTK-Fix fehlgeschlagen"' in page
    assert '"RTK-Status unbekannt"' in page
    assert 'hero(summary,"RTK-Status",rtkLabel(t.rtk_state))' in page
    assert 'metric(grid,"RTK-Status (Rohwert)",text(t.rtk_state))' in page
    assert '"RTK nicht gestartet"' in page
    assert "0 bedeutet nicht zwingend" in page
    assert "Satellitenanzahlen sind gemeldete Werte" in page


def test_cockpit_is_read_only_and_does_not_invent_hms_explanations():
    page = render_operations()
    assert '"HMS · "+warnings.length+" zuletzt gemeldete Hinweise"' in page
    assert 'alert.message&&alert.message!==alert.code?' in page
    assert '"Code: "+text(alert.code)' in page
    assert 'textContent=String(text)' in page
    assert "0x16070042" not in page
    assert "innerHTML" not in page
    assert "Authorization" not in page
    assert "localStorage" not in page
