"""Regressions for invalid radiometry, API errors and tilted ground projection."""
import math

import numpy as np
import pytest

from aeronexus.multispectral import (MultispectralError, band_metadata, compute_layer,
                                     read_band, rectify, relative_reflectance)
from aeronexus.thermal_geo import ground_footprint
from test_multispectral import HEADERS, UUID, api, band, ms, xmp


@pytest.mark.parametrize("status", ["0", "3", "", "nan"])
def test_invalid_sunlight_status_blocks_reflectance(status):
    dn, info = read_band(band(20000))
    cal = band_metadata(xmp().decode().replace('LS_status="1"', f'LS_status="{status}"'))["calibration"]
    with pytest.raises(MultispectralError, match="Sonnenlichtsensor"):
        relative_reflectance(dn, info, cal)


@pytest.mark.parametrize("status", [1, 2])
def test_valid_sunlight_states_are_supported(status):
    dn, info = read_band(band(20000))
    cal = {**band_metadata(info["xmp"])["calibration"], "sunlight_sensor_status": status}
    assert np.isfinite(relative_reflectance(dn, info, cal)).all()


@pytest.mark.parametrize("irradiance", [None, 0, .5, 1])
def test_missing_or_placeholder_irradiance_is_not_replaced(irradiance):
    dn, info = read_band(band(20000))
    cal = {**band_metadata(info["xmp"])["calibration"], "irradiance": irradiance}
    with pytest.raises(MultispectralError):
        relative_reflectance(dn, info, cal)


def test_black_and_saturated_pixels_are_masked_before_statistics():
    dn, info = read_band(band(20000))
    cal = band_metadata(info["xmp"])["calibration"]
    dn = np.array([[0, 3199, 3200, 3201, 65535]], np.uint16)
    out = relative_reflectance(dn, info, cal)
    assert np.isnan(out[0, [0, 1, 2, 4]]).all()
    assert np.isfinite(out[0, 3])


def test_negative_reflectance_does_not_turn_into_high_ndvi():
    bands = {"NIR": np.array([[.5, .5, np.nan]], np.float32),
             "Red": np.array([[-.1, .1, .1]], np.float32)}
    out = compute_layer("ndvi", bands)
    assert np.isnan(out[0, 0]) and np.isnan(out[0, 2])
    assert out[0, 1] == pytest.approx(2 / 3)
    # LCI is a ratio with a different denominator: legitimate values below -1
    # must also survive, instead of being silently clipped.
    bands = {k: np.array([[v]], np.float32) for k, v in
             {"NIR": .1, "RedEdge": .8, "Red": .1}.items()}
    assert compute_layer("lci", bands)[0, 0] == pytest.approx(-3.5)


def test_incompatible_band_shapes_have_domain_error():
    with pytest.raises(MultispectralError, match="dimensions"):
        compute_layer("ndvi", {"NIR": np.ones((2, 2)), "Red": np.ones((3, 3))})


@pytest.mark.parametrize("hmatrix", [[0] * 9, [1, 2], [float("nan")] * 9])
def test_bad_homography_is_a_controlled_error(hmatrix):
    with pytest.raises(MultispectralError, match="HMatrix"):
        rectify(np.ones((10, 10), np.float32), {"h_matrix": hmatrix})


def test_projective_horizon_pixels_are_nan_without_runtime_warnings():
    with np.errstate(all="raise"):
        grid = rectify(np.ones((10, 10), np.float32),
                       {"h_matrix": [1, 0, 0, 0, 1, 0, 1, 0, 1]}, scale=1)
    assert np.isnan(grid[:, 1]).all()


def test_zero_dewarp_focal_length_has_controlled_error():
    with pytest.raises(MultispectralError, match="DewarpData"):
        rectify(np.ones((10, 10), np.float32), {"dewarp": [0] * 9})


def test_catalog_warns_about_invalid_sensor(ms):
    key = "wayline/org_a_1.tiff"
    data, etag = ms.client.items[key]
    ms.client.items[key] = (data.replace(b'LS_status="1"', b'LS_status="0"'), etag + "bad")
    ms.media.scan(ms.client, "dji-cloud")
    ms.catalog.scan(ms.client, "dji-cloud")
    assert any("Sonnenlichtsensor ungültig" in w for w in ms.catalog.capture(UUID)["warnings"])
    assert ms.compute_missing_summaries() == 0
    assert ms.summary_failures == [UUID]
    assert ms.map_items()["items"][0]["ndvi"] is None


def test_singular_homography_returns_422_instead_of_500(api, ms):
    key = "wayline/org_a_1.tiff"
    data, etag = ms.client.items[key]
    ms.client.items[key] = (data.replace(b'CalibratedHMatrix="1,0,0,0,1,0,0,0,1"',
                                        b'CalibratedHMatrix="0,0,0,0,0,0,0,0,0"'), etag + "bad")
    ms.media.scan(ms.client, "dji-cloud")
    ms.catalog.scan(ms.client, "dji-cloud")
    for suffix in ("", "/grid"):
        response = api.get(f"/api/v1/multispectral/captures/{UUID}/layers/ndvi{suffix}", headers=HEADERS)
        assert response.status_code == 422
        assert "HMatrix" in response.json()["detail"]


def test_quality_change_invalidates_persisted_map_summaries(ms, monkeypatch):
    import aeronexus.multispectral as module
    ms.catalog.scan(ms.client, "dji-cloud")
    ms.analysis(UUID, "ndvi", scale=4)
    assert ms.map_items()["items"][0]["ndvi"] is not None
    monkeypatch.setattr(module, "PROCESSING_VERSION", "new-quality-rules")
    assert ms.map_items()["items"][0]["ndvi"] is None


def test_pitch_projection_uses_ground_ray_intersection():
    pos = {"latitude": 49.1, "longitude": 8.5, "relative_altitude_m": 100}
    normal = ground_footprint(pos, {"pitch_deg": -90, "yaw_deg": 0}, 60, 40,
                              account_for_pitch=True)
    tilted = ground_footprint(pos, {"pitch_deg": -75, "yaw_deg": 0}, 60, 40,
                              account_for_pitch=True)
    assert normal != tilted
    # The north edge is at h*tan(15deg+20deg), the south edge at
    # h*tan(15deg-20deg); this is a trapezoid, not a translated rectangle.
    assert (tilted[0][0] - pos["latitude"]) * 111320 == pytest.approx(
        100 * math.tan(math.radians(35)), abs=.002)
    assert (tilted[3][0] - pos["latitude"]) * 111320 == pytest.approx(
        100 * math.tan(math.radians(-5)), abs=.002)
    assert tilted[1][1] - tilted[0][1] > tilted[2][1] - tilted[3][1]
    # Thermal consumers retain their existing rectangular projection.
    assert ground_footprint(pos, {"pitch_deg": -75, "yaw_deg": 0}, 60, 40) == normal
