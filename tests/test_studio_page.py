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
    assert "leaflet@1.9.4" in page
    assert 'integrity="sha256-' in page
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
