"""DJI Mavic 3M multispectral: TIFF/XMP parsing, DJI radiometry, alignment, catalogue, API."""
import struct

import numpy as np
import pytest
from fastapi.testclient import TestClient

from aeronexus.minio_media_index import DjiMediaIndex, media_id
from aeronexus.multispectral import (MultispectralError, MultispectralService,
                                     band_metadata, compute_layer, item_metadata, layer_stats,
                                     read_band, rectify, relative_reflectance, tiff_structure)
from aeronexus.multispectral_page import render_multispectral_page

from test_thermal import APP_MODULE, HEADERS, TOKEN, FakeMinio, segment

UUID = "c0b53d9a3dd045db9c77bf6c744608d7"
SERIAL = "1581F5FKD0000TEST"
W, H = 40, 30


def xmp(band="NIR", uuid=UUID, irradiance=900.0, gain=2.0, exposure=1000, sga=1.0,
        lat="+49.1", lon="+8.5", model="M3M", vignetting="0,0,0,0,0,0",
        hmatrix="1,0,0,0,1,0,0,0,1", dewarp="2023-01-09;1000,1000,0,0,0,0,0,0,0"):
    return (f'<x:xmpmeta><rdf:Description tiff:Model="{model}" xmp:CreateDate="2026-10-15T14:02:40+02:00" '
            f'drone-dji:ImageSource="MS_{band}_CAMERA" drone-dji:GpsStatus="RTK" '
            f'drone-dji:GpsLatitude="{lat}" drone-dji:GpsLongitude="{lon}" '
            f'drone-dji:RelativeAltitude="+30.0" drone-dji:GimbalPitchDegree="-90.0" '
            f'drone-dji:CaptureUUID="{uuid}" drone-dji:BandName="{band}" drone-dji:BandFreq="860(+/-26)nm" '
            f'drone-dji:BlackLevel="3200" drone-dji:SensorGain="{gain}" drone-dji:ExposureTime="{exposure}" '
            f'drone-dji:SensorGainAdjustment="{sga}" drone-dji:Irradiance="{irradiance}" drone-dji:LS_status="1" '
            f'drone-dji:VignettingData="{vignetting}" drone-dji:CalibratedOpticalCenterX="{W / 2}" '
            f'drone-dji:CalibratedOpticalCenterY="{H / 2}" drone-dji:DewarpData="{dewarp}" '
            f'drone-dji:CalibratedHMatrix="{hmatrix}" drone-dji:DroneSerialNumber="{SERIAL}" '
            f'drone-dji:NTRIPHost="ntrip.example"/></x:xmpmeta>').encode()


def tiff(dn, meta: bytes) -> bytes:
    """Minimal little-endian baseline TIFF: 16-bit, one strip, XMP tag 700."""
    h, w = dn.shape
    entries = [(256, 4, 1, w), (257, 4, 1, h), (258, 3, 1, 16), (259, 3, 1, 1),
               (277, 3, 1, 1), (273, 4, 1, 0), (279, 4, 1, w * h * 2), (700, 1, len(meta), 0)]
    ifd_size = 2 + len(entries) * 12 + 4
    xmp_off = 8 + ifd_size
    strip_off = xmp_off + len(meta)
    out = bytearray(b"II*\x00" + struct.pack("<I", 8) + struct.pack("<H", len(entries)))
    for tag, typ, n, value in entries:
        if tag == 273:
            value = strip_off
        if tag == 700:
            out += struct.pack("<HHII", tag, typ, n, xmp_off)
        elif typ == 3:
            out += struct.pack("<HHIHH", tag, typ, n, value, 0)
        else:
            out += struct.pack("<HHII", tag, typ, n, value)
    out += struct.pack("<I", 0) + meta + dn.astype("<u2").tobytes()
    return bytes(out)


def band(value, **kw):
    return tiff(np.full((H, W), value, dtype=np.uint16), xmp(**kw))


def rgb_jpeg(uuid=UUID):
    meta = (f'<x:xmpmeta><rdf:Description tiff:Model="M3M" drone-dji:CaptureUUID="{uuid}" '
            f'xmp:CreateDate="2026-10-15T14:02:40+02:00"/></x:xmpmeta>').encode()
    return (b"\xff\xd8" + segment(0xE1, b"http://ns.adobe.com/xap/1.0/\x00" + meta)
            + segment(0xDA, b"\x00" * 4) + b"\xff\xd9")


def expected_reflectance(dn, gain=2.0, exposure=1000, sga=1.0, irradiance=900.0):
    return ((dn - 3200) / 65536) / (gain * exposure / 1e6) * sga / irradiance


# -------------------------------------------------------------- parsing ----

def test_tiff_roundtrip_and_partial_header():
    dn = np.arange(W * H, dtype=np.uint16).reshape(H, W)
    data = tiff(dn, xmp())
    decoded, info = read_band(data)
    assert np.array_equal(decoded, dn) and info["bits"] == 16
    head = tiff_structure(data[:400], partial=True)
    assert (head["width"], head["height"]) == (W, H)
    for bad in (b"", b"II*\x00\xff\xff\xff\xff", b"\xff\xd8not tiff"):
        with pytest.raises(MultispectralError):
            tiff_structure(bad)
    with pytest.raises(MultispectralError):
        read_band(data[:-10])


def test_band_metadata_whitelisted():
    meta = band_metadata(xmp().decode())
    assert meta["band"] == "NIR" and meta["capture_uuid"] == UUID and meta["model"] == "M3M"
    cal = meta["calibration"]
    assert cal["black_level"] == 3200 and cal["irradiance"] == 900 and cal["h_matrix"][0] == 1
    assert len(cal["dewarp"]) == 9 and len(cal["vignetting"]) == 6
    assert SERIAL not in repr(meta) and "ntrip" not in repr(meta)
    assert band_metadata(xmp(lat="+0.0", lon="+0.0").decode())["position"] is None
    assert band_metadata(xmp(uuid="not-a-uuid").decode())["capture_uuid"] is None


def test_item_metadata_filters_non_m3m():
    assert item_metadata("x.TIF", band(10000))["kind"] == "band"
    assert item_metadata("x.TIF", band(10000, model="P4M")) is None
    assert item_metadata("DJI_1_0001_D.JPG", rgb_jpeg())["kind"] == "rgb"
    assert item_metadata("x.TIF", b"junk") is None


# ----------------------------------------------------------- radiometry ----

def test_relative_reflectance_follows_dji_eq9_and_sunlight_sensor():
    dn, info = read_band(band(20000, gain=2.0, exposure=1000, sga=1.25, irradiance=500.0))
    cal = band_metadata(info["xmp"])["calibration"]
    out = relative_reflectance(dn, info, cal)
    assert out[5, 5] == pytest.approx(expected_reflectance(20000, sga=1.25, irradiance=500.0), rel=1e-5)


def test_vignetting_polynomial_grows_with_radius():
    dn, info = read_band(band(20000, vignetting="0.01,0,0,0,0,0"))
    cal = band_metadata(info["xmp"])["calibration"]
    out = relative_reflectance(dn, info, cal)
    centre = expected_reflectance(20000)
    assert out[15, 20] == pytest.approx(centre, rel=1e-5)  # r = 0 at the optical centre
    assert out[15, 30] == pytest.approx(centre * (1 + 0.01 * 10), rel=1e-5)


def test_rectify_identity_shift_and_outside_is_nan():
    image = np.tile(np.arange(W, dtype=np.float32), (H, 1))
    cal = band_metadata(xmp().decode())["calibration"]
    same = rectify(image, cal, scale=1)
    assert np.allclose(same[2:-2, 2:-2], image[2:-2, 2:-2], atol=1e-4)
    shifted = rectify(image, {**cal, "h_matrix": [1, 0, 3, 0, 1, 0, 0, 0, 1]}, scale=1)
    assert shifted[10, 20] == pytest.approx(17.0, abs=1e-4)  # designed x 20 <- real x 17
    assert np.isnan(shifted[10, 0])
    assert rectify(image, cal, scale=2).shape == (H // 2, W // 2)


def test_indices():
    bands = {"NIR": np.full((2, 2), 0.5, np.float32), "Red": np.full((2, 2), 0.1, np.float32),
             "Green": np.full((2, 2), 0.2, np.float32), "RedEdge": np.full((2, 2), 0.3, np.float32)}
    assert compute_layer("ndvi", bands)[0, 0] == pytest.approx(0.4 / 0.6)
    assert compute_layer("gndvi", bands)[0, 0] == pytest.approx(0.3 / 0.7)
    assert compute_layer("ndre", bands)[0, 0] == pytest.approx(0.2 / 0.8)
    assert compute_layer("lci", bands)[0, 0] == pytest.approx(0.2 / 0.6)
    zero = {k: np.zeros((2, 2), np.float32) for k in bands}
    assert np.isnan(compute_layer("ndvi", zero)).all()
    stats = layer_stats("ndvi", np.array([[-0.5, 0.1], [0.5, 0.9]], np.float32))
    assert sum(c["share"] for c in stats["classes"]) == pytest.approx(1.0)
    with pytest.raises(MultispectralError):
        layer_stats("ndvi", np.full((2, 2), np.nan, np.float32))


# ------------------------------------------------- catalogue / service ----

NIR, RED = 40000, 12000
ITEMS = {
    "wayline/org_a_1.tiff": (band(NIR, band="NIR"), "e1"),
    "wayline/org_b_1.tiff": (band(RED, band="Red", irradiance=1000.0), "e2"),
    "sd/x/DJI_20261015140240_0001_MS_G.TIF": (band(15000, band="Green"), "e3"),
    "sd/y/DJI_20261015140240_0001_MS_RE.TIF": (band(30000, band="RedEdge"), "e4"),
    "sd/z/DJI_20261015140240_0001_D.JPG": (rgb_jpeg(), "e5"),
    "other/foreign.tif": (band(1, model="P4M", uuid="f" * 32), "e6"),
}


@pytest.fixture
def ms(tmp_path, monkeypatch):
    monkeypatch.setenv("AERONEXUS_WORKSPACE_DIR", str(tmp_path / "ws"))
    client = FakeMinio(dict(ITEMS))
    index = DjiMediaIndex(tmp_path / "ws")
    index.scan(client, "dji-cloud")
    service = MultispectralService(index, settings_factory=lambda: type("S", (), {"bucket": "dji-cloud"})(),
                                   client_factory=lambda s: client)
    service.client = client
    return service


def test_catalog_groups_bands_by_capture_uuid(ms):
    report = ms.catalog.scan(ms.client, "dji-cloud")
    assert report["captures"] == 1 and report["failed"] == 0  # non-M3M TIFF is not catalogued
    captures = ms.catalog.captures()
    assert len(captures) == 1
    c = captures[0]
    assert sorted(c["bands"]) == ["Green", "NIR", "Red", "RedEdge"]
    assert c["rgb"]["id"] == media_id("dji-cloud", "sd/z/DJI_20261015140240_0001_D.JPG")
    assert c["layers"][:4] == ["ndvi", "gndvi", "ndre", "lci"] and not c["warnings"]
    assert ms.catalog.path.stat().st_mode & 0o077 == 0
    assert ms.catalog.scan(ms.client, "dji-cloud")["read"] == 0  # unchanged ETags skipped


def test_service_ndvi_matches_formula(ms):
    ms.catalog.scan(ms.client, "dji-cloud")
    a = ms.analysis(UUID, "ndvi", scale=2)
    nir, red = expected_reflectance(NIR), expected_reflectance(RED, irradiance=1000.0)
    assert a["stats"]["median"] == pytest.approx((nir - red) / (nir + red), abs=1e-4)
    assert (a["width"], a["height"]) == (W // 2, H // 2) and a["label"] == "NDVI"
    with pytest.raises(MultispectralError):
        ms.layer(UUID, "evi")


def test_missing_band_and_unknown_capture(ms):
    del ms.client.items["wayline/org_b_1.tiff"]
    ms.media.scan(ms.client, "dji-cloud")
    ms.catalog.scan(ms.client, "dji-cloud")
    c = ms.catalog.capture(UUID)
    assert "ndvi" not in c["layers"] and "ndre" in c["layers"] and c["warnings"]
    with pytest.raises(MultispectralError):
        ms.layer(UUID, "ndvi")
    with pytest.raises(MultispectralError):
        ms.catalog.capture("0" * 32)


@pytest.fixture
def api(ms, monkeypatch):
    ms.catalog.scan(ms.client, "dji-cloud")
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    monkeypatch.setattr(APP_MODULE.app.state, "ms_service", ms, raising=False)
    return TestClient(APP_MODULE.app)


def test_api(api):
    assert api.get("/api/v1/multispectral/captures").status_code == 401
    body = api.get("/api/v1/multispectral/captures", headers=HEADERS).json()
    assert body["total"] == 1 and "object_key" not in repr(body) and SERIAL not in repr(body)
    r = api.get(f"/api/v1/multispectral/captures/{UUID}/layers/ndre?scale=2", headers=HEADERS)
    assert r.status_code == 200 and r.json()["label"] == "NDRE"
    g = api.get(f"/api/v1/multispectral/captures/{UUID}/layers/ndvi/grid?scale=4", headers=HEADERS)
    assert g.status_code == 200 and (g.headers["x-grid-width"], g.headers["x-grid-height"]) == ("10", "7")
    assert len(g.content) == 10 * 7 * 4
    assert api.get(f"/api/v1/multispectral/captures/{UUID}/layers/evi", headers=HEADERS).status_code == 404
    assert api.get("/api/v1/multispectral/captures/" + "0" * 32 + "/layers/ndvi",
                   headers=HEADERS).status_code == 404


def test_page_static_and_linked_everywhere(api):
    r = api.get("/multispectral")
    assert r.status_code == 200 and "connect-src 'self'" in r.headers["content-security-policy"]
    html = render_multispectral_page()
    assert "Authorization" not in html and 'aria-current="page">Multispektral' in html
    from aeronexus.dji_media_page import render_dji_media_page
    from aeronexus.operations_page import render_operations
    from aeronexus.status_page import render_page
    from aeronexus.studio_page import render_studio
    from aeronexus.thermal_page import render_thermal_page
    for page in (render_operations(), render_studio(), render_page(30), render_dji_media_page(),
                 render_thermal_page()):
        assert 'href="/multispectral"' in page
