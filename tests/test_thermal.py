"""Thermography: R-JPEG parsing, DJI Thermal SDK adapter (fake dji_irp), service and API."""
from array import array
from datetime import datetime, timezone
import importlib
import re
import stat
import struct
import subprocess
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from aeronexus.minio_media_index import DjiMediaIndex, media_id
from aeronexus.thermal import (ThermalChanged, ThermalError, ThermalNotFound, ThermalService,
                               jpeg_segments, temperature_stats, thermal_metadata, visual_keys)
from aeronexus.thermal_page import render_thermal_page
from aeronexus.thermal_sdk import (MeasureParams, ThermalSdk, ThermalSdkError,
                                   ThermalSdkSettings, ThermalSdkUnavailable)


TOKEN = "thermal-module-test-only-dashboard-token-123456"
HEADERS = {"Authorization": "Bearer " + TOKEN}
APP_MODULE = importlib.import_module("aeronexus.app")
SERIAL = "1581F5FJD0000TEST"


def segment(marker: int, body: bytes) -> bytes:
    return bytes([0xFF, marker]) + struct.pack(">H", len(body) + 2) + body


def rjpeg(width=4, height=2, raw=None, *, lat="+49.160329099", lon="+8.595456832",
          model="M3T", ir_header=True) -> bytes:
    xmp = (f'<x:xmpmeta><rdf:Description tiff:Make="DJI" tiff:Model="{model}" '
           f'xmp:CreateDate="2024-10-22T17:23:29+02:00" drone-dji:ImageSource="InfraredCamera" '
           f'drone-dji:GpsStatus="RTK" drone-dji:GpsLatitude="{lat}" drone-dji:GpsLongitude="{lon}" '
           f'drone-dji:AbsoluteAltitude="+202.938" drone-dji:RelativeAltitude="+44.477" '
           f'drone-dji:GimbalPitchDegree="-89.90" drone-dji:GimbalYawDegree="+12.70" '
           f'drone-dji:DroneSerialNumber="{SERIAL}" drone-dji:CameraSerialNumber="5L4SLTEST" '
           f'drone-dji:NTRIPHost="ntrip.example" drone-dji:LRFStatus="Normal" '
           f'drone-dji:LRFTargetDistance="12.5" drone-dji:LRFTargetLat="49.1604" '
           f'drone-dji:LRFTargetLon="8.5955"/></x:xmpmeta>').encode()
    raw = raw if raw is not None else b"\x00\x48" * (width * height)
    parts = [b"\xff\xd8", segment(0xE1, b"Exif\x00\x00II*\x00"),
             segment(0xE1, b"http://ns.adobe.com/xap/1.0/\x00" + xmp)]
    parts += [segment(0xE3, raw[i:i + 65000]) for i in range(0, len(raw), 65000)]
    if ir_header:
        parts.append(segment(0xE4, b"\xff\xd2\xd1\xffiirp\x00" + b"\x00" * 32))
    parts.append(segment(0xC0, struct.pack(">BHHB", 8, height, width, 3) + b"\x00" * 9))
    parts.append(segment(0xDA, b"\x00" * 10) + b"\x00\xff\xd9")
    return b"".join(parts)


# --------------------------------------------------------------- parsing ----

def test_metadata_is_whitelisted_and_typed():
    meta = thermal_metadata(rjpeg())
    assert meta["model"] == "M3T" and meta["radiometric"] is True
    assert (meta["width"], meta["height"], meta["raw_width"]) == (4, 2, 4)
    assert meta["position"]["latitude"] == pytest.approx(49.160329099)
    assert meta["position"]["relative_altitude_m"] == pytest.approx(44.477)
    assert meta["gimbal"]["pitch_deg"] == pytest.approx(-89.9)
    assert meta["laser_range"]["distance_m"] == 12.5
    text = repr(meta)
    assert SERIAL not in text and "5L4SLTEST" not in text and "ntrip" not in text


def test_super_resolution_preview_with_half_size_raw_is_radiometric():
    meta = thermal_metadata(rjpeg(8, 4, raw=b"\x01\x48" * 8, model="M4T"))
    assert meta["radiometric"] and (meta["raw_width"], meta["raw_height"]) == (4, 2)


def test_non_radiometric_and_no_fix_position():
    assert not thermal_metadata(rjpeg(raw=b"\x00" * 6))["radiometric"]
    assert not thermal_metadata(rjpeg(ir_header=False))["radiometric"]
    assert thermal_metadata(rjpeg(lat="-0.000000333", lon="+0.000000655"))["position"] is None


@pytest.mark.parametrize("data", [b"", b"PNG", b"\xff\xd8\x00\x00",
                                  b"\xff\xd8\xff\xe1\xff\xff abc"])
def test_malformed_jpeg_rejected(data):
    with pytest.raises(ThermalError):
        jpeg_segments(data)


def test_visual_pairing_candidates():
    assert visual_keys("w/DJI_1_0001_T.JPG") == ["w/DJI_1_0001_V.JPG", "w/DJI_1_0001_W.JPG",
                                                 "w/DJI_1_0001_Z.JPG"]
    assert visual_keys("w/dji_1_0001_t.jpg")[0] == "w/dji_1_0001_v.jpg"
    assert visual_keys("w/DJI_1_0001_V.JPG") == []


def test_temperature_stats():
    grid = array("f", [10.0, 12.0, 30.5, 11.0, 9.5, 20.0])
    s = temperature_stats(3, 2, grid)
    assert (s["min_c"], s["max_c"]) == (9.5, 30.5)
    assert s["hotspot"] == {"x": 2, "y": 0} and s["coldspot"] == {"x": 1, "y": 1}
    assert s["mean_c"] == pytest.approx(15.5)
    with pytest.raises(ThermalError):
        temperature_stats(4, 2, grid)


# ------------------------------------------------------------------- SDK ----

def test_measure_params_validated_and_only_overrides_passed():
    assert MeasureParams().arguments() == []
    p = MeasureParams(emissivity=0.9, distance=3)
    assert p.arguments() == ["--distance", "3", "--emissivity", "0.9"]
    assert p.overrides() == {"distance": 3.0, "emissivity": 0.9}
    for bad in ({"emissivity": 0.05}, {"distance": 30}, {"humidity": 10},
                {"reflection": float("nan")}, {"ambient": True}):
        with pytest.raises(ValueError):
            MeasureParams(**bad)


FAKE_IRP = f"""#!{sys.executable}
import struct, sys
args = sys.argv[1:]
if args == ["-V"]:
    print("APP version : V1.7"); sys.exit(0)
src, out = args[args.index("-s") + 1], args[args.index("-o") + 1]
data = open(src, "rb").read()
mode = data[-8:-2]
emiss = float(args[args.index("--emissivity") + 1]) if "--emissivity" in args else 0.95
values = [20.0 + i + (emiss - 0.95) * 10 for i in range(8)]
if mode == b"BADSZE":
    values = values[:3]
if mode == b"NANNAN":
    values[0] = float("nan")
print("      image  width : 4"); print("      image height : 2")
if mode == b"FAILED":
    print("Test done with return code -7"); sys.exit(0)
open(out, "wb").write(struct.pack("<8f" if len(values) == 8 else "<3f", *values))
print("Test done with return code 0")
"""


@pytest.fixture
def sdk_dir(tmp_path, monkeypatch):
    home = tmp_path / "tsdk"
    (home / "bin").mkdir(parents=True)
    tool = home / "bin" / "dji_irp"
    tool.write_text(FAKE_IRP)
    tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
    (home / "bin" / "libdirp.so").write_bytes(b"\x7fELF")
    monkeypatch.setenv("AERONEXUS_DJI_TSDK_DIR", str(home))
    monkeypatch.setenv("AERONEXUS_DJI_TSDK_RUNNER", "native")
    return home


def test_settings_fail_closed(tmp_path, monkeypatch):
    with pytest.raises(ThermalSdkUnavailable):
        ThermalSdkSettings.from_env({})
    with pytest.raises(ThermalSdkUnavailable):
        ThermalSdkSettings.from_env({"AERONEXUS_DJI_TSDK_DIR": "relative/path"})
    with pytest.raises(ThermalSdkUnavailable):
        ThermalSdkSettings.from_env({"AERONEXUS_DJI_TSDK_DIR": str(tmp_path)})


def test_settings_box64_requires_box64_and_x86_libs(sdk_dir, tmp_path):
    env = {"AERONEXUS_DJI_TSDK_DIR": str(sdk_dir), "AERONEXUS_DJI_TSDK_RUNNER": "box64",
           "AERONEXUS_BOX64": str(tmp_path / "missing-box64")}
    with pytest.raises(ThermalSdkUnavailable):
        ThermalSdkSettings.from_env(env)
    box = tmp_path / "box64"
    box.write_text("#!/bin/sh\n")
    box.chmod(0o755)
    libs = tmp_path / "x86"
    libs.mkdir()
    env.update(AERONEXUS_BOX64=str(box), AERONEXUS_BOX64_X86_LIBS=str(libs))
    with pytest.raises(ThermalSdkUnavailable):
        ThermalSdkSettings.from_env(env)
    (libs / "libstdc++.so.6").write_bytes(b"")
    settings = ThermalSdkSettings.from_env(env)
    assert settings.command("-V")[0] == str(box)
    child = settings.child_env("/tmp/x")
    assert child["BOX64_LD_LIBRARY_PATH"] == f"{sdk_dir / 'bin'}:{libs}"
    assert not any(key.startswith("AERONEXUS") for key in child)


def test_sdk_layout_from_extracted_zip(tmp_path):
    root = tmp_path / "sdk"
    tool = root / "utility/bin/linux/release_x64/dji_irp"
    lib = root / "tsdk-core/lib/linux/release_x64/libdirp.so"
    for p in (tool, lib):
        p.parent.mkdir(parents=True)
        p.write_bytes(b"")
    s = ThermalSdkSettings.from_env({"AERONEXUS_DJI_TSDK_DIR": str(root),
                                     "AERONEXUS_DJI_TSDK_RUNNER": "native"})
    assert s.tool == tool and s.lib_dir == lib.parent


def test_measure_with_fake_dji_irp(sdk_dir):
    sdk = ThermalSdk.from_env()
    assert sdk.version() == {"tool": "V1.7", "dirp_api": None, "runner": "native"}
    w, h, grid = sdk.measure(rjpeg())
    assert (w, h) == (4, 2) and list(grid)[:2] == [20.0, 21.0]
    _, _, grid = sdk.measure(rjpeg(), MeasureParams(emissivity=0.45))
    assert grid[0] == pytest.approx(15.0)


@pytest.mark.parametrize("tail", [b"BADSZE", b"NANNAN", b"FAILED"])
def test_measure_rejects_bad_sdk_output(sdk_dir, tail):
    with pytest.raises(ThermalSdkError):
        ThermalSdk.from_env().measure(rjpeg() + tail + b"\xff\xd9")


def test_measure_rejects_non_jpeg_and_timeouts(sdk_dir, monkeypatch):
    sdk = ThermalSdk.from_env()
    with pytest.raises(ThermalSdkError):
        sdk.measure(b"not a jpeg")

    def slow(*a, **k):
        raise subprocess.TimeoutExpired("dji_irp", 1)
    monkeypatch.setattr(subprocess, "run", slow)
    with pytest.raises(ThermalSdkError, match="timed out"):
        sdk.measure(rjpeg())


# --------------------------------------------------------------- service ----

class Stream:
    def __init__(self, data):
        self.data = data

    def read(self, n):
        return self.data[:n]

    def close(self):
        pass

    def release_conn(self):
        pass


class FakeMinio:
    def __init__(self, items):
        self.items = items
        self.gets = 0

    def list_objects(self, bucket, recursive):
        for key, (data, etag) in self.items.items():
            yield SimpleNamespace(object_name=key, size=len(data), etag=etag, is_dir=False,
                                  last_modified=datetime(2026, 10, 2, tzinfo=timezone.utc))

    def stat_object(self, bucket, key):
        data, etag = self.items[key]
        return SimpleNamespace(size=len(data), etag=etag)

    def get_object(self, bucket, key, offset=0, length=None):
        self.gets += 1
        data = self.items[key][0]
        return Stream(data[offset:offset + length] if length else data)


THERMAL = "sdimport-A/aaa/DJI_20241022172329_0438_T.JPG"
VISUAL = "sdimport-A/bbb/DJI_20241022172329_0438_V.JPG"
PREVIEW = "wayline/DJI_20261002180010_0003_T.JPG"


@pytest.fixture
def service(tmp_path, sdk_dir, monkeypatch):
    monkeypatch.setenv("AERONEXUS_WORKSPACE_DIR", str(tmp_path / "workspace"))
    client = FakeMinio({THERMAL: (rjpeg(), "e1"), VISUAL: (b"\xff\xd8visual", "e2"),
                        PREVIEW: (rjpeg(raw=b""), "e3")})
    index = DjiMediaIndex(tmp_path / "workspace")
    index.scan(client, "dji-cloud")
    settings = SimpleNamespace(bucket="dji-cloud")
    svc = ThermalService(index, settings_factory=lambda: settings,
                         client_factory=lambda s: client)
    svc.client = client
    return svc


def test_service_lists_only_thermal_images_with_visual_pair(service):
    result = service.list()
    assert result["total"] == 2
    by_name = {m["name"]: m for m in result["media"]}
    assert by_name["DJI_20241022172329_0438_T.JPG"]["visual_id"] == media_id("dji-cloud", VISUAL)
    assert by_name["DJI_20261002180010_0003_T.JPG"]["visual_id"] is None
    assert service.list(query="0438")["total"] == 1


def test_service_analysis_measures_and_caches(service):
    item = media_id("dji-cloud", THERMAL)
    a = service.analysis(item)
    m = a["measurement"]
    assert (m["width"], m["height"], m["max_c"], m["min_c"]) == (4, 2, 27.0, 20.0)
    assert m["hotspot"] == {"x": 3, "y": 1} and m["parameter_overrides"] == {}
    gets = service.client.gets
    service.analysis(item)
    assert service.client.gets == gets  # file and measurement cached
    assert service.analysis(item, MeasureParams(emissivity=0.85))["measurement"]["min_c"] == 19.0


def test_service_non_radiometric_returns_metadata_only(service):
    a = service.analysis(media_id("dji-cloud", PREVIEW))
    assert a["measurement"] is None and a["radiometric"] is False
    assert "radiometrisch" in a["measurement_error"]


def test_service_refuses_unknown_non_thermal_and_changed(service):
    with pytest.raises(ThermalNotFound):
        service.analysis(media_id("dji-cloud", VISUAL))
    with pytest.raises(ThermalNotFound):
        service.analysis("0" * 64)
    service.client.items[THERMAL] = (rjpeg(), "replaced")
    with pytest.raises(ThermalChanged):
        service.analysis(media_id("dji-cloud", THERMAL))


def test_service_without_sdk_reports_unavailable(service, monkeypatch):
    monkeypatch.delenv("AERONEXUS_DJI_TSDK_DIR")
    service._sdk = None
    a = service.analysis(media_id("dji-cloud", THERMAL))
    assert a["sdk"]["available"] is False and a["measurement"] is None


# ------------------------------------------------------------------- API ----

@pytest.fixture
def client(service, monkeypatch):
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    monkeypatch.setattr(APP_MODULE.app.state, "thermal_service", service, raising=False)
    return TestClient(APP_MODULE.app)


def test_api_requires_viewer_access(client):
    for path in ("/api/v1/thermal/status", "/api/v1/thermal/images"):
        assert client.get(path).status_code == 401


def test_api_status_list_analysis_and_grid(client):
    status = client.get("/api/v1/thermal/status", headers=HEADERS).json()
    assert status["sdk"]["available"] and status["thermal_images"] == 2
    images = client.get("/api/v1/thermal/images", headers=HEADERS).json()
    assert all("object_key" not in m and "bucket" not in m for m in images["media"])
    item = media_id("dji-cloud", THERMAL)
    r = client.get(f"/api/v1/thermal/images/{item}/analysis?emissivity=0.85", headers=HEADERS)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    assert r.json()["measurement"]["parameter_overrides"] == {"emissivity": 0.85}
    assert SERIAL not in r.text
    g = client.get(f"/api/v1/thermal/images/{item}/temperatures", headers=HEADERS)
    assert g.status_code == 200 and g.headers["content-type"] == "application/octet-stream"
    assert (g.headers["x-thermal-width"], g.headers["x-thermal-height"]) == ("4", "2")
    assert struct.unpack("<8f", g.content)[7] == 27.0


def test_api_error_mapping(client):
    item = media_id("dji-cloud", THERMAL)
    assert client.get(f"/api/v1/thermal/images/{item}/analysis?emissivity=2",
                      headers=HEADERS).status_code == 422
    assert client.get("/api/v1/thermal/images/" + "0" * 64 + "/analysis",
                      headers=HEADERS).status_code == 404
    preview = media_id("dji-cloud", PREVIEW)
    assert client.get(f"/api/v1/thermal/images/{preview}/temperatures",
                      headers=HEADERS).status_code == 422


def test_thermal_page_is_static_and_locked_down(client):
    r = client.get("/thermal")
    assert r.status_code == 200
    csp = r.headers["content-security-policy"]
    assert "connect-src 'self'" in csp and "frame-ancestors 'none'" in csp
    html = render_thermal_page()
    assert "Authorization" not in html and "Bearer " not in html
    assert 'aria-current="page">Thermografie' in html
    assert "/api/v1/thermal/images" in html and not re.search(r"\d{14}_\d{4}_T", html)


def test_every_ui_links_the_thermal_tab():
    from aeronexus.dji_media_page import render_dji_media_page
    from aeronexus.operations_page import render_operations
    from aeronexus.status_page import render_page
    from aeronexus.studio_page import render_studio
    for html in (render_operations(), render_studio(), render_page(30), render_dji_media_page()):
        assert 'href="/thermal"' in html
