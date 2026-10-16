"""Chrome desktop map, gallery and offline mission planner UI contracts."""
from html.parser import HTMLParser

from aeronexus.studio_page import render_studio


class _HTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.nodes = []

    def handle_starttag(self, tag, attrs):
        self.nodes.append((tag, dict(attrs)))


def test_studio_has_desktop_map_media_fleet_tabs():
    page = render_studio()
    tags = _HTML()
    tags.feed(page)
    ids = {attrs["id"] for tag, attrs in tags.nodes if "id" in attrs}
    for element_id in (
        "map", "map-layer", "map-pane", "media-pane", "fleet-pane",
        "mission-panel", "mission-list", "save-mission", "delete-mission",
        "point-list", "point-editor", "export-mission", "media-file",
        "gallery", "media-search", "fleet-grid",
    ):
        assert element_id in ids


def test_leaflet_version_is_pinned_and_has_integrity():
    page = render_studio()
    parser = _HTML()
    parser.feed(page)
    leaflet_css = [
        attrs for tag, attrs in parser.nodes if tag == "link"
        and attrs.get("rel") == "stylesheet"
        and attrs.get("href") == "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css"
    ]
    assert len(leaflet_css) == 1
    # Official Leaflet 1.9.4 quick-start canonical CSS SHA-256.
    # A previous invalid hash caused Chrome to reject Leaflet CSS,
    # leaving map tiles scattered across the viewport.
    assert leaflet_css[0]["integrity"] == (
        "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
    )
    assert "crossorigin" in leaflet_css[0]
    leaflet_js = [
        attrs for tag, attrs in parser.nodes if tag == "script"
        and attrs.get("src") == "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"
    ]
    assert len(leaflet_js) == 1
    assert leaflet_js[0]["integrity"] == (
        "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
    )
    assert "#map{height:100%" in page
    assert "https://tile.openstreetmap.org/" in page
    assert "https://server.arcgisonline.com/" in page
    assert "OpenStreetMap contributors" in page


def test_wpml_planner_is_explicitly_offline_and_cautious():
    page = render_studio()
    assert "keine Flugausführung" in page
    assert "DJI Pilot 2" in page
    assert "wpmz/template.kml" in page
    assert "wpmz/waylines.wpml" in page
    assert "take_photo" in page
    assert "mission.waypoints" in page
    assert "fetch" in page
    assert "localStorage" not in page
    assert "innerHTML" not in page
    assert "DJI Dock" not in page


def test_media_files_are_transferred_only_to_local_workspace():
    page = render_studio()
    assert '/api/v1/studio/media' in page
    assert 'URL.createObjectURL' in page
    assert 'revokeMedia()' in page
    assert 'accept=".jpg,.jpeg,.png,.webp,.mp4' in page
    assert "25 MiB" in page


def test_lan_workspace_auto_loads_without_any_browser_token():
    page = render_studio()
    assert 'id="auth-token"' not in page
    assert 'id="login"' not in page
    assert 'id="logout"' not in page
    assert 'accessToken' not in page
    assert 'headerToken' not in page
    assert 'Authorization' not in page
    assert 'loadWorkspace();' in page
    assert 'await Promise.allSettled([loadMedia(),loadFleet()]);' in page
    assert 'async function api(path,options={})' in page
    assert 'textContent' in page


def test_wpml_reimport_exposed_for_saved_aeronexus_routes():
    page = render_studio()
    assert 'id="import-kmz"' in page
    assert 'id="import-mission"' in page
    assert '/api/v1/studio/missions/import.kmz' in page
    assert 'async function importMission()' in page
    assert 'AeroNexus-KMZ als bearbeitbare Mission importiert' in page


def test_fresh_mission_map_starts_in_76694_forst_at_town_zoom():
    page = render_studio()
    assert 'label:"76694 Forst (Baden)"' in page
    assert 'latitude:49.1533,longitude:8.58417,zoom:15' in page
    assert '[HOME_VIEW.latitude,HOME_VIEW.longitude],HOME_VIEW.zoom' in page
    assert 'id="map-home"' in page
    assert 'function centerOnForst()' in page
    assert 'addEventListener("click",centerOnForst)' in page
    assert 'setView([51.16,10.45],6)' not in page


def test_map_uses_esri_satellite_by_default_and_handles_osm_block():
    page = render_studio()
    assert '<option value="satellite" selected>' in page
    assert 'mapTile=mapTiles.satellite.addTo(map);' in page
    assert 'referrerPolicy:"strict-origin-when-cross-origin"' in page
    assert 'mapTiles.street.on("tileerror"' in page
    assert 'setMapLayer("satellite")' in page
    assert 'mapWarning(' in page
    assert 'Straßenkarten-Kacheln nicht verfügbar' in page
    assert "OpenStreetMap contributors" in page


def test_route_close_control_is_reversible_and_stored_as_mission_data():
    page = render_studio()
    assert 'id="close-route" type="checkbox"' in page
    assert 'mission.close_route=e.target.checked' in page
    assert 'mission.close_route=$("close-route").checked' in page
    assert '$("close-route").checked=mission.close_route===true' in page
    assert 'close_route:false,waypoints:[]' in page
    assert 'function closingAddsWaypoint()' in page
    assert 'function resolvedWaypoints()' in page
    assert 'if(closingAddsWaypoint())' in page
    assert 'points.push({...points[0],take_photo:false})' in page
    assert 'mission.close_route' in page
    assert 'async function saveMission()' in page


def test_closed_route_draws_real_return_leg_without_changing_rth_action():
    page = render_studio()
    assert 'L.polyline([[last.latitude,last.longitude],[first.latitude,first.longitude]]' in page
    assert 'dashArray:"10 9"' in page
    assert 'Rückflug zum ersten Wegpunkt · echter DJI-WPML-Wegpunkt' in page
    assert 'ein zusätzlicher Wegpunkt angelegt' in page
    assert 'Return-to-Home-Einstellung bleibt unabhängig' in page
    assert 'mission.finish_action=$("mission-finish").value' in page
    assert 'Geschlossene Route:' in page
    assert 'mindestens 3 unterschiedliche Wegpunkte' in page


def test_route_analysis_is_live_read_only_and_covers_closing_segment():
    page = render_studio()
    assert 'id="route-distance"' in page
    assert 'id="route-duration"' in page
    assert 'id="route-legs"' in page
    assert 'id="route-return"' in page
    assert 'id="route-analysis-warning"' in page
    assert 'function geoDistanceMeters(a,b)' in page
    assert 'function routeMetrics(points,closeRoute,speedMps)' in page
    assert 'function formatRouteDuration(seconds)' in page
    assert 'function updateRouteAnalysis()' in page
    assert 'const analysis=updateRouteAnalysis();' in page
    assert 'for(const id of FORM_IDS)' in page
    assert 'if(id==="mission-speed")updateRouteAnalysis();' in page
    assert 'Keine Freigabe zum Fliegen.' in page
    assert 'Nur ideale horizontale Reisezeit' in page
    assert 'if(closeRoute&&n===route.length-1&&route.length>=3' in page
    # Calculation requires neither an extra backend API nor flight commands.
    assert '/api/v1/flight/command' not in page
    assert 'innerHTML' not in page



def test_editor_has_history_dirty_indicator_and_precise_coordinates():
    page = render_studio()
    for marker in (
        'id="undo-edit"', 'id="redo-edit"', 'id="editor-dirty"',
        'id="insert-midpoint"', 'id="copy-point"',
        'function editorSnapshot()', 'function historyRecord(group=null)',
        'function undoEdit()', 'function redoEdit()', 'function historySaved(signature)',
        'function allowDiscard()', 'function midpointCoordinates(a,b)',
        'function insertMidpoint()', 'window.addEventListener("beforeunload"',
        'window.addEventListener("keydown"', 'isTextEditing(e.target)',
        'mission.waypoints.splice(selected+1,0,point)',
        'p.latitude.toFixed(7)+", "+p.longitude.toFixed(7)',
        'mission.waypoints[n]={...mission.waypoints[n],latitude:lat,longitude:lon}',
    ):
        assert marker in page
    assert 'HISTORY_LIMIT=60' in page
    assert 'innerHTML' not in page
    assert 'localStorage' not in page
    assert 'sessionStorage' not in page


def test_unsaved_editor_changes_guard_switches_and_saved_baseline():
    page = render_studio()
    assert 'if(!skipConfirm&&!allowDiscard()){updateMissionSelect();return false;}' in page
    assert 'if(!skipConfirm&&!allowDiscard()){updateMissionSelect();return false;}' in page
    assert 'if(!missionId||!allowDiscard()||' in page
    assert 'if(!allowDiscard())return;' in page
    assert 'newMission({skipConfirm:true})' in page
    assert 'await loadMission(record.id,{skipConfirm:true})' in page
    assert 'historySaved(saveSignature)' in page
    assert 'historyReset()' in page
    assert 'editorSignature(editorSnapshot())!==startSignature' in page
    assert 'e.returnValue=""' in page
    assert 'HISTORY_LIMIT=60' in page
    assert '/api/v1/flight/command' not in page
