"""M3M 4-band stacking (after mirrormapper/m3m-image-stacking): alignment, GeoTIFF, CLI, API."""
import struct
import zlib

import numpy as np
import pytest

from aeronexus.m3m_stack import (BAND_ORDER, georeference, main, phase_shift, shift_image,
                                 stack_bands, stack_to_geotiff, write_geotiff)
from aeronexus.multispectral import MultispectralError, tiff_structure

from test_multispectral import H, NIR, RED, UUID, W, band, expected_reflectance
from test_multispectral import api, ms  # noqa: F401  (pytest fixtures)
from test_thermal import HEADERS


def texture(h=120, w=160, seed=1):
    rng = np.random.default_rng(seed)
    base = rng.random((h // 4, w // 4)).astype(np.float32)
    return np.kron(base, np.ones((4, 4), np.float32)) + rng.random((h, w)).astype(np.float32) * 0.05


def test_phase_correlation_recovers_subpixel_shift_and_aligns():
    ref = texture()
    moving = shift_image(ref, -3.0, 5.5)  # moving(y, x) = ref(y - 3, x + 5.5)
    dy, dx, conf = phase_shift(ref, moving, max_shift=20)
    assert dy == pytest.approx(3.0, abs=0.3) and dx == pytest.approx(-5.5, abs=0.3) and conf > 8
    aligned = shift_image(moving, dy, dx)
    inner = (slice(10, -10), slice(10, -10))
    assert np.nanmean(np.abs(aligned[inner] - ref[inner])) < np.nanmean(np.abs(moving[inner] - ref[inner])) / 3


def test_phase_correlation_rejects_large_or_unclear_shifts():
    ref = texture()
    assert phase_shift(ref, shift_image(ref, 0, 40), max_shift=20)[2] == 0.0
    noise = np.random.default_rng(5).random(ref.shape).astype(np.float32)
    assert phase_shift(ref, noise, max_shift=20)[2] < 8


def bands(**overrides):
    values = {"NIR": NIR, "Green": 15000, "Red": RED, "RedEdge": 30000}
    files = {b: band(v, band=b, irradiance=1000.0 if b == "Red" else 900.0) for b, v in values.items()}
    files.update(overrides)
    return files


def test_stack_order_values_crop_and_products():
    result = stack_bands(bands(), scale=1, refine=True, crop_margin=2)
    cube = result["bands"]
    assert cube.shape[0] == 4 and result["crop"]["width"] < W and result["crop"]["height"] < H
    assert cube[0, 5, 5] == pytest.approx(expected_reflectance(NIR), rel=1e-4)  # band 1 = NIR
    assert cube[2, 5, 5] == pytest.approx(expected_reflectance(RED, irradiance=1000.0), rel=1e-4)
    assert all(not s["applied"] for s in result["shifts"].values())  # flat test bands: nothing to align
    dn = stack_bands(bands(), product="dn", refine=False, crop_margin=0)
    assert dn["shifts"] == {} and dn["bands"][0, 5, 5] == pytest.approx(NIR)


def test_stack_refuses_mixed_or_incomplete_captures():
    with pytest.raises(MultispectralError):
        stack_bands({b: f for b, f in bands().items() if b != "Red"})
    with pytest.raises(MultispectralError):
        stack_bands(bands(Red=band(RED, band="Red", uuid="f" * 32)))
    with pytest.raises(MultispectralError):
        stack_bands(bands(Red=band(RED, band="Green")))
    with pytest.raises(MultispectralError):  # no valid sunlight sensor -> no reflectance product
        stack_bands(bands(NIR=band(NIR, band="NIR", irradiance=1.0)))
    assert stack_bands(bands(NIR=band(NIR, band="NIR", irradiance=1.0)), product="dn")["bands"].shape[0] == 4


def test_geotiff_structure_tiles_and_metadata():
    cube = np.arange(4 * 300 * 270, dtype=np.float32).reshape(4, 300, 270)
    data = write_geotiff(cube, descriptions=list(BAND_ORDER), metadata={"BAND_ORDER": "NIR,Green,Red,RedEdge"},
                         nodata="nan")
    info = tiff_structure(data)
    assert (info["width"], info["height"], info["bits"], info["compression"], info["samples"]) == (270, 300, 32, 8, 4)
    bo = "<"
    offset = struct.unpack("<I", data[4:8])[0]
    count = struct.unpack("<H", data[offset:offset + 2])[0]
    tags = {}
    for i in range(count):
        tag, typ, n, raw = struct.unpack(bo + "HHI4s", data[offset + 2 + 12 * i:offset + 14 + 12 * i])
        tags[tag] = (typ, n, raw)
    assert sorted(tags) == list(tags)  # TIFF requires ascending tag order
    n_tiles = tags[324][1]
    assert n_tiles == 4 * 2 * 2  # planar: 4 bands x 2x2 tiles of 256
    offs = struct.unpack(f"<{n_tiles}I", data[struct.unpack("<I", tags[324][2])[0]:][:4 * n_tiles])
    cnts = struct.unpack(f"<{n_tiles}I", data[struct.unpack("<I", tags[325][2])[0]:][:4 * n_tiles])
    tile = np.frombuffer(zlib.decompress(data[offs[4]:offs[4] + cnts[4]]), "<f4").reshape(256, 256)
    assert np.array_equal(tile, cube[1, :256, :256])  # band 2, first tile
    meta = data[struct.unpack("<I", tags[42112][2])[0]:].split(b"\0", 1)[0].decode()
    assert '<Item name="DESCRIPTION" sample="0" role="description">NIR</Item>' in meta
    assert 34264 not in tags  # no georeference requested


def test_georeference_nadir_maps_corner_and_centre():
    result = {"optics": {"hfov_deg": 61.69, "vfov_deg": 48.26, "width": 2592, "height": 1944},
              "position": {"latitude": 49.16, "longitude": 8.59, "relative_altitude_m": 50.0},
              "gimbal": {"pitch_deg": -90.0, "yaw_deg": 30.0}, "scale": 2,
              "crop": {"x": 25, "y": 25, "width": 1246, "height": 922}}
    a, b, _, d, e, f, _, h = georeference(result)[:8]
    lon_c, lat_c = a * (648 - 25) + b * (486 - 25) + d, e * (648 - 25) + f * (486 - 25) + h
    assert lon_c == pytest.approx(8.59, abs=1e-9) and lat_c == pytest.approx(49.16, abs=1e-9)
    assert georeference({**result, "gimbal": {"pitch_deg": 0.0, "yaw_deg": 0.0}}) is None


def test_stack_to_geotiff_tags_and_georef():
    result = stack_bands(bands(), refine=False, crop_margin=0)
    data = stack_to_geotiff(result)
    assert b"BAND_ORDER\">NIR,Green,Red,RedEdge" in data and b"relative reflectance" in data
    assert b"DJI_CAPTURE_UUID\">" + UUID.encode() in data
    assert b"approximate, nadir footprint" in data  # test bands: 30 m, pitch -90


@pytest.mark.parametrize("pitch", [-80.0, -75.0, -105.0, -89.9, float("nan"), None])
def test_tilted_stack_has_no_misleading_affine_georeference(pitch):
    result = stack_bands(bands(), refine=False, crop_margin=0)
    result["gimbal"]["pitch_deg"] = pitch
    assert georeference(result) is None
    data = stack_to_geotiff(result)
    offset = struct.unpack("<I", data[4:8])[0]
    n = struct.unpack_from("<H", data, offset)[0]
    tags = {struct.unpack_from("<H", data, offset + 2 + i * 12)[0] for i in range(n)}
    assert not tags.intersection({34264, 34735})  # neither transform nor CRS
    assert b"requires exact -90 degree pitch" in data
    assert tiff_structure(data)["samples"] == 4  # image export is still available


def test_cli_stacks_local_folder(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("AERONEXUS_WORKSPACE_DIR", str(tmp_path / "ws"))
    src, out = tmp_path / "in", tmp_path / "out"
    src.mkdir()
    for name, data in bands().items():
        (src / f"DJI_20261015140240_0001_MS_{ {'NIR': 'NIR', 'Green': 'G', 'Red': 'R', 'RedEdge': 'RE'}[name]}.TIF").write_bytes(data)
    (src / "other_MS_G.TIF").write_bytes(band(1, band="Green", uuid="e" * 32))  # incomplete capture
    assert main([str(src), "-o", str(out), "--crop-margin", "0"]) == 0
    written = list(out.glob("*_aligned.tif"))
    assert len(written) == 1 and tiff_structure(written[0].read_bytes())["samples"] == 4
    assert "incomplete capture" in capsys.readouterr().err
    assert main([str(src), "-o", str(out), "--crop-margin", "0"]) == 1  # exists, no --force


def test_stack_api(api, ms):  # noqa: F811
    r = api.get(f"/api/v1/multispectral/captures/{UUID}/stack.tif?scale=1&refine=false", headers=HEADERS)
    assert r.status_code == 200 and r.headers["content-type"] == "image/tiff"
    assert r.headers["content-disposition"].startswith('attachment; filename="m3m_c0b53d9a_reflectance')
    assert tiff_structure(r.content)["samples"] == 4
    assert api.get(f"/api/v1/multispectral/captures/{UUID}/stack.tif?product=raw",
                   headers=HEADERS).status_code == 422
    assert api.get("/api/v1/multispectral/captures/" + "0" * 32 + "/stack.tif",
                   headers=HEADERS).status_code == 404
    assert api.get(f"/api/v1/multispectral/captures/{UUID}/stack.tif").status_code == 401
