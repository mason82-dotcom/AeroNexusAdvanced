"""Pilot 2 map overlay remains opt-in and must not edit any mission data."""
from aeronexus.studio_page import render_studio


def test_pilot_map_layer_has_explicit_user_toggle_and_readonly_source():
    page = render_studio()
    assert 'id="pilot2-map-toggle"' in page
    assert 'aria-pressed="false"' in page
    assert 'async function togglePilot2MapLayer()' in page
    snippet = page[page.index("async function togglePilot2MapLayer()"):page.index("function centerOnForst()")]
    assert 'api("/api/v1/local-cloud/map-elements")' in snippet
    assert "interactive:false" in snippet
    assert 'if(!pilot2LayerVisible)' in snippet
    assert 'mission.waypoints.push' not in snippet
    assert 'saveMission' not in snippet
    assert 'innerHTML' not in snippet
    assert 'properties:{}' in snippet
    assert "pilot2MapLayer.clearLayers()" in snippet
    assert 'pilot2MapLayer=L.layerGroup()' in page
    assert 'id="pilot2-map-toggle"' in page


def test_map_layer_does_not_become_part_of_dji_wayline_export():
    page = render_studio()
    assert "const EMPTY=()" in page
    assert "waypointsLayer=L.layerGroup().addTo(map)" in page
    assert "pilot2MapLayer=L.layerGroup()" in page
    assert 'export-mission' in page
