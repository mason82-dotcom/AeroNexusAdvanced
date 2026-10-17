"""Validate Phase 19's literal EPSG:4326 DEM sample-centre metadata."""
import pytest

from aeronexus.terrain_preview import geotiff_preview
from test_phase17_pi_readiness import stub_gdal


def test_wgs84_sample_centres_match_native_four_by_four(monkeypatch):
    made,freed=stub_gdal(monkeypatch,shape=(4,4),
        transform=(8.5,.0001,0,49.2,0,-.0001))
    geo={"old":"stale"}
    grid=geotiff_preview(b"II*\x00test",geo_info=geo)
    assert geo["crs"]=="EPSG:4326"
    assert geo["reference"]=="sample-centres"
    assert geo["west_lon"]==pytest.approx(8.50005)
    assert geo["north_lat"]==pytest.approx(49.19995)
    assert geo["lon_step_deg"]==pytest.approx(.0001)
    assert geo["lat_step_deg"]==pytest.approx(-.0001)
    assert geo["vertical_reference"]=="unspecified"
    assert "old" not in geo
    assert grid.x_step_m>0
    assert made==freed


def test_downsampled_dem_centre_spacing_uses_native_dimensions(monkeypatch):
    stub_gdal(monkeypatch,shape=(96,96),
        transform=(8.5,.0001,0,49.2,0,-.0001))
    geo={}
    grid=geotiff_preview(b"II*\x00test",geo_info=geo)
    assert len(grid.heights_m)==48
    assert len(grid.heights_m[0])==48
    assert geo["west_lon"]==pytest.approx(8.5001)
    assert geo["north_lat"]==pytest.approx(49.1999)
    assert geo["lon_step_deg"]==pytest.approx(.0002)
    assert geo["lat_step_deg"]==pytest.approx(-.0002)
    assert grid.y_step_m==pytest.approx(111132*.0002)


def test_projected_geo_is_not_misrepresented_as_wgs84(monkeypatch):
    stub_gdal(monkeypatch,projected=True)
    geo={"stale":"entry"}
    grid=geotiff_preview(b"II*\x00test",geo_info=geo)
    assert grid.heights_m==[[200,200],[200,200]]
    assert geo=={}


@pytest.mark.parametrize("transform",[
    (179.999,.01,0,49.2,0,-.01),
    (8.5,.25,0,80.0,0,-.001),
])
def test_unsafe_wgs84_extents_do_not_generate_overlay_coordinates(monkeypatch,transform):
    stub_gdal(monkeypatch,shape=(4,4),transform=transform)
    geo={}
    grid=geotiff_preview(b"II*\x00test",geo_info=geo)
    assert grid.heights_m[0][0]==200
    assert geo=={}
