"""Real GeoTIFF/COG fixtures: reprojection, masks, privacy and source identity."""
from hashlib import sha256
import json
import math
from pathlib import Path
import struct
import zlib

import pytest

np = pytest.importorskip("numpy")
rio = pytest.importorskip("rasterio")
from rasterio.enums import ColorInterp
from rasterio.shutil import copy as rio_copy
from rasterio.transform import from_bounds
from rasterio.warp import transform_bounds

from aeronexus.raster_results import (RasterChanged, RasterError, RasterNotFound,
                                      RasterResults, tile_bounds)


@pytest.fixture
def results(tmp_path):
    source = tmp_path / "inputs"
    source.mkdir()
    return RasterResults(tmp_path / "private", source)


def raster(path, *, crs="EPSG:4326", data=None, nodata=-9999., rgb=False, bounds=None):
    if data is None:
        data = np.full((1, 32, 32), .5, dtype="float32")
        data[0, :8, :8] = nodata
        data[0, 8:16, 8:16] = 0  # valid zero must stay visible
    if data.ndim == 2:
        data = data[None]
    bounds = bounds or (8.58, 49.15, 8.59, 49.16)
    if crs and crs != "EPSG:4326":
        bounds = transform_bounds("EPSG:4326", crs, *bounds)
    with rio.open(path, "w", driver="GTiff", width=data.shape[2], height=data.shape[1],
                  count=data.shape[0], dtype=data.dtype, crs=crs, nodata=nodata,
                  transform=from_bounds(*bounds, data.shape[2], data.shape[1]),
                  tiled=True, blockxsize=16, blockysize=16) as ds:
        ds.write(data)
        if rgb:
            ds.colorinterp = (ColorInterp.red, ColorInterp.green, ColorInterp.blue)
    return path


def xyz(lon=8.585, lat=49.155, z=16):
    x = int((lon + 180) / 360 * 2**z)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * 2**z)
    return z, x, y


def decode_png(png):
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    offset, body = 8, b""
    while offset < len(png):
        size = struct.unpack(">I", png[offset:offset + 4])[0]
        kind = png[offset + 4:offset + 8]
        data = png[offset + 8:offset + 8 + size]
        if kind == b"IHDR":
            assert struct.unpack(">IIBBBBB", data) == (256, 256, 8, 6, 0, 0, 0)
        if kind == b"IDAT":
            body += data
        offset += size + 12
    raw = np.frombuffer(zlib.decompress(body), dtype="uint8").reshape(256, 1025)
    assert np.all(raw[:, 0] == 0)
    return raw[:, 1:].reshape(256, 256, 4)


def test_scan_sources_unchanged_and_catalog_private(results):
    path = raster(results.source / "field_ndvi.tif")
    original = sha256(path.read_bytes()).hexdigest()
    result = results.scan()
    assert result["indexed"] == 1 and result["rejected"] == 0
    item = results.list()["items"][0]
    assert item["kind"] == "ndvi" and item["tiled"] and not item["cog"]
    assert item["bands"][0]["nodata"] == -9999
    assert item["bounds"] == pytest.approx([8.58, 49.15, 8.59, 49.16])
    assert not results.path.stat().st_mode & 0o077
    assert str(results.source) not in json.dumps(item)
    assert sha256(path.read_bytes()).hexdigest() == original
    assert sorted(p.name for p in results.source.iterdir()) == [path.name]


def test_actual_cog_and_projected_crs(results):
    src = raster(results.source / "source.tif", crs="EPSG:32632")
    cog = results.source / "field_cog.tif"
    rio_copy(src, cog, driver="COG", BLOCKSIZE=128)
    assert results.scan()["indexed"] == 2
    item = next(i for i in results.list()["items"] if i["filename"] == "field_cog.tif")
    assert item["cog"] and item["crs"] == "EPSG:32632"
    rgba = decode_png(results.tile(item["id"], *xyz(), low=-1, high=1, version=item["version"]))
    assert np.any(rgba[:, :, 3] == 255)


def test_masks_valid_zero_and_outside_coverage(results):
    raster(results.source / "field_ndvi.tif")
    results.scan()
    item = results.list()["items"][0]
    rgba = decode_png(results.tile(item["id"], *xyz(z=14), palette="gray", low=0, high=1))
    assert np.any(rgba[:, :, 3] == 0)
    assert np.any(rgba[:, :, 3] == 255)
    assert np.any((rgba[:, :, 0] == 0) & (rgba[:, :, 3] == 255))
    assert np.any((rgba[:, :, 0] > 100) & (rgba[:, :, 3] == 255))
    outside = decode_png(results.tile(item["id"], 5, 0, 0))
    assert not np.any(outside[:, :, 3])


def test_nan_and_nodata_never_render_as_measurements(results):
    data = np.full((32, 32), np.nan, dtype="float32")
    raster(results.source / "empty.tif", data=data, nodata=np.nan)
    results.scan()
    item = results.list()["items"][0]
    with pytest.raises(RasterError, match="Stichproben"):
        results.statistics(item["id"])
    assert not np.any(decode_png(results.tile(item["id"], *xyz()))[:, :, 3])


def test_rgb_tags_and_scalar_ranges_do_not_change_pixel_values(results):
    data = np.stack([np.full((32, 32), x, dtype="uint8") for x in (200, 100, 50)])
    raster(results.source / "rgb.tif", data=data, nodata=None, rgb=True)
    results.scan()
    item = results.list()["items"][0]
    assert item["rgb_bands"] == [1, 2, 3]
    rgba = decode_png(results.tile(item["id"], *xyz(), mode="rgb", low=0, high=255))
    visible = rgba[rgba[:, :, 3] == 255]
    assert visible.size and np.all(visible[:, :3] == [200, 100, 50])
    a = results.tile(item["id"], *xyz(), band=1, low=0, high=255, palette="gray")
    b = results.tile(item["id"], *xyz(), band=1, low=0, high=1000, palette="gray")
    assert a != b


def test_band_scale_offset_and_statistics_are_bounded(results):
    path = raster(results.source / "scaled.tif", data=np.full((32, 32), 10, dtype="int16"), nodata=-9999)
    with rio.open(path, "r+") as ds:
        ds.scales, ds.offsets = (2.,), (5.,)
    results.scan()
    item = results.list()["items"][0]
    stats = results.statistics(item["id"])
    assert stats["min"] == stats["max"] == 25
    assert stats["p02"] < stats["p98"]
    assert stats["approximate"] and stats["sample_count"] <= 256 * 256
    rgba = decode_png(results.tile(item["id"], *xyz(), low=0, high=50, palette="gray"))
    assert np.all(rgba[rgba[:, :, 3] == 255, 0] == 127)


def test_changed_file_cannot_serve_stale_cached_tiles_or_statistics(results):
    path = raster(results.source / "field.tif")
    results.scan()
    old = results.list()["items"][0]
    results.tile(old["id"], *xyz())
    results.statistics(old["id"])
    raster(path, data=np.full((32, 32), .8, dtype="float32"))
    with pytest.raises(RasterChanged):
        results.tile(old["id"], *xyz())
    with pytest.raises(RasterChanged):
        results.statistics(old["id"])
    results.scan()
    current = results.list()["items"][0]
    assert old["id"] == current["id"] and old["version"] != current["version"]
    with pytest.raises(RasterChanged):
        results.get(old["id"], old["version"])
    assert results.statistics(current["id"])["min"] == pytest.approx(.8)


def test_symlink_path_traversal_and_missing_sources(results, tmp_path):
    target = raster(tmp_path / "outside.tif")
    (results.source / "linked.tif").symlink_to(target)
    (results.source / "not-raster.tif").write_text("not a raster")
    raster(results.source / "no-crs.tif", crs=None)
    report = results.scan()
    assert report["indexed"] == 0 and report["rejected"] == 3
    assert results.list()["items"] == []
    with pytest.raises(RasterNotFound):
        results.get("../outside.tif")
    with pytest.raises(RasterNotFound):
        results.get("0" * 32)
    linked_dir = tmp_path / "link-dir"
    linked_dir.symlink_to(results.source, target_is_directory=True)
    with pytest.raises(RasterError, match="Verzeichnis"):
        RasterResults(results.root, linked_dir)


def test_pagination_filter_and_missing_file_reindex(results):
    for n in range(3):
        raster(results.source / f"field_{n}.tif")
    results.scan()
    assert results.list(limit=2, offset=999)["offset"] == 2
    assert results.list(query="field_1")["total"] == 1
    item = results.list()["items"][0]
    (results.source / item["filename"]).unlink()
    with pytest.raises(RasterNotFound):
        results.get(item["id"])
    results.scan()
    assert results.list()["total"] == 2


@pytest.mark.parametrize("coords", [(-1, 0, 0), (23, 0, 0), (2, 4, 0), (2, 0, -1)])
def test_tile_coordinates_bounded(coords):
    with pytest.raises(RasterError):
        tile_bounds(*coords)


@pytest.mark.parametrize("options", [{"band": 0}, {"mode": "vrt"}, {"palette": "oops"},
                                    {"low": float("nan")}, {"low": 1, "high": 1}, {"mode": "rgb"}])
def test_invalid_display_requests_rejected(results, options):
    raster(results.source / "scalar.tif")
    results.scan()
    item = results.list()["items"][0]
    with pytest.raises(RasterError):
        results.tile(item["id"], *xyz(), **options)


def test_failed_directory_or_limit_scan_preserves_previous_catalog(results, monkeypatch):
    import aeronexus.raster_results as module
    raster(results.source / 'good.tif')
    results.scan()
    previous = results.list()
    monkeypatch.setattr(module, 'MAX_FILES', 1)
    raster(results.source / 'second.tif')
    with pytest.raises(RasterError, match='500'):
        results.scan()
    assert results.list() == previous
    moved = results.source.with_name('moved')
    results.source.rename(moved)
    with pytest.raises(RasterError, match='fehlt'):
        results.scan()
    assert results.list() == previous


def test_internal_mask_and_alpha_remain_transparent(results):
    path = raster(results.source / 'masked.tif', data=np.zeros((32, 32), dtype='uint8'), nodata=None)
    with rio.Env(GDAL_TIFF_INTERNAL_MASK=True), rio.open(path, 'r+') as ds:
        mask = np.full((32, 32), 255, dtype='uint8')
        mask[:, :16] = 0
        ds.write_mask(mask)
    results.scan()
    item = results.list()['items'][0]
    rgba = decode_png(results.tile(item['id'], *xyz(z=14), palette='gray'))
    visible = rgba[:, :, 3] > 0
    assert np.any(visible) and not np.all(visible)
    assert np.all(rgba[visible, 0] == 0)
