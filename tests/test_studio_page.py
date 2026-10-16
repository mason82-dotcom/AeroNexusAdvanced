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


def test_private_content_loaded_only_with_bearer_token():
    page = render_studio()
    assert 'headers:{...headerToken()' in page
    assert '"Authorization":"Bearer "+accessToken' in page
    assert 'if(!accessToken)throw' in page
    assert 'function logout()' in page
    assert 'epoch++' in page
    assert 'textContent' in page
