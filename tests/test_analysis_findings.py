"""Regression tests for the 2026-10-17 analysis findings (MS compute limit,
tilted thermal footprints, scoped GDAL exception mode)."""
import importlib
import math
import threading
import warnings

import pytest
from fastapi.testclient import TestClient

from aeronexus.multispectral import MultispectralBusy
from aeronexus.thermal_geo import footprint
from aeronexus.terrain_preview import TerrainUnavailable, geotiff_preview

from test_multispectral import UUID, ms  # noqa: F401  (fixture)
from test_thermal import HEADERS, TOKEN


def thermal_meta(pitch):
    return {"model": "M3T", "raw_width": 640, "raw_height": 512,
            "position": {"latitude": 49.16, "longitude": 8.59, "relative_altitude_m": 40.0},
            "gimbal": {"pitch_deg": pitch, "yaw_deg": 0.0}}


def test_thermal_footprint_uses_tilted_projection():
    nadir, tilted = footprint(thermal_meta(-90)), footprint(thermal_meta(-80))
    centre = lambda corners: sum(c[0] for c in corners) / 4  # noqa: E731
    assert centre(nadir) == pytest.approx(49.16, abs=1e-7)
    shift_m = (centre(tilted) - 49.16) * 111_320
    assert 40 * math.tan(math.radians(10)) * 0.9 < shift_m < 40 * math.tan(math.radians(10)) * 1.3
    far, near = tilted[0][0] - 49.16, 49.16 - tilted[3][0]
    assert far > near  # the far edge of a forward-tilted view is longer


def test_multispectral_band_processing_is_single_flight(ms):
    ms.catalog.scan(ms.client, "dji-cloud")
    ms.COMPUTE_WAIT_SECONDS = 0.05
    assert ms._compute.acquire(timeout=1)
    try:
        with pytest.raises(MultispectralBusy):
            ms.layer(UUID, "ndvi", scale=4)
    finally:
        ms._compute.release()
    ms.COMPUTE_WAIT_SECONDS = 5
    before = ms.client.gets
    results, errors = [], []

    def run():
        try:
            results.append(ms.layer(UUID, "ndvi", scale=4)[1])
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(exc)
    threads = [threading.Thread(target=run) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert not errors and len(results) == 3
    assert ms.client.gets - before == 2  # NIR and Red read once; waiting requests use the cache


def test_busy_maps_to_503_with_retry_after(ms, monkeypatch):
    app = importlib.import_module("aeronexus.app").app
    ms.catalog.scan(ms.client, "dji-cloud")
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    monkeypatch.setattr(app.state, "ms_service", ms, raising=False)
    ms.COMPUTE_WAIT_SECONDS = 0.05
    assert ms._compute.acquire(timeout=1)
    try:
        r = TestClient(app).get(f"/api/v1/multispectral/captures/{UUID}/layers/ndvi?scale=4",
                                headers=HEADERS)
    finally:
        ms._compute.release()
    assert r.status_code == 503 and r.headers["retry-after"] == "10"


def test_gdal_errors_are_scoped_and_mapped():
    pytest.importorskip("osgeo.gdal")
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        for bad in (b"II*\x00" + b"\x00" * 100, b"MM\x00*" + b"garbage" * 10):
            with pytest.raises(ValueError, match="Invalid or unreadable GeoTIFF"):
                geotiff_preview(bad)


def test_terrain_unavailable_is_not_masked(monkeypatch):
    class FakeGdal:
        OF_RASTER = OF_READONLY = 0

        class ExceptionMgr:
            def __init__(self, **_):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        @staticmethod
        def FileFromMemBuffer(path, content):
            raise TerrainUnavailable("GDAL needs NumPy in the same Python environment")

        @staticmethod
        def Unlink(path):
            raise RuntimeError("not there")
    import sys
    import types
    monkeypatch.setitem(sys.modules, "osgeo", types.SimpleNamespace(gdal=FakeGdal))
    with pytest.raises(TerrainUnavailable):
        geotiff_preview(b"II*\x00" + b"\x00" * 10)
