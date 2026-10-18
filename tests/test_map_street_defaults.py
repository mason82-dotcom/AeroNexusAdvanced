"""Default basemap contracts for every AeroNexusAdvanced Leaflet view.

These are source-rendering tests (no network, DJI devices, or persisted state).
Street maps must initialize on every map, satellite remains optional/fallback.
"""

from aeronexus.dji_media_page import render_dji_media_page
from aeronexus.multispectral_page import render_multispectral_page
from aeronexus.operations_page import render_operations
from aeronexus.studio_page import render_studio
from aeronexus.thermal_page import render_thermal_page


def test_mission_studio_and_embedded_csv_preview_start_with_osm():
    html = render_studio()
    assert '<option value="street" selected>' in html
    assert '<option value="satellite">' in html
    assert 'mapTile=mapTiles.street.addTo(map);' in html
    assert '$("map-layer").value="street";' in html
    assert 'mapTile=mapTiles.satellite.addTo(map);' not in html
    assert 'setMapLayer("satellite");' in html  # Retain network-error fallback.
    assert 'referrerPolicy:"strict-origin-when-cross-origin"' in html
    csv = html.split("function csvShowMap(){", 1)[1].split(
        "async function previewCsv()", 1)[0]
    assert 'L.tileLayer("https://tile.openstreetmap.org/' in csv
    assert 'SATELLITE_TILE_URL' not in csv
    assert 'Straßenkarten-Kacheln nicht verfügbar' in csv


def test_operations_center_starts_with_street_layer_and_retains_esri_fallback():
    html = render_operations()
    assert '<option value="street" selected>' in html
    assert '<option value="satellite">' in html
    assert 'tileLayer=mapLayers.street.addTo(map);' in html
    assert 'tileLayer=mapLayers.satellite.addTo(map);' not in html
    assert 'chooseTile("satellite");' in html
    assert 'referrerPolicy:"strict-origin-when-cross-origin"' in html


def test_thermal_map_starts_with_streets():
    html = render_thermal_page()
    assert 'osm.addTo(map);L.control.layers({"Straßenkarte":osm,"Satellit":sat})' in html
    assert 'sat.addTo(map);' not in html
    assert 'referrerPolicy:"strict-origin-when-cross-origin"' in html


def test_multispectral_map_starts_with_streets():
    html = render_multispectral_page()
    assert 'osm.addTo(map);L.control.layers({"Straßenkarte":osm,"Satellit":sat})' in html
    assert 'sat.addTo(map);' not in html
    assert 'referrerPolicy:"strict-origin-when-cross-origin"' in html


def test_dji_media_map_starts_with_streets():
    html = render_dji_media_page()
    assert 'osm.addTo(photoMap);L.control.layers({"Straßenkarte":osm,"Satellit":sat})' in html
    assert 'sat.addTo(photoMap);' not in html
    assert 'referrerPolicy:"strict-origin-when-cross-origin"' in html
