"""Thermal map geometry/geo index and PV inspection (IEC TS 62446-3 orientation)."""
from array import array
import math

import pytest

from aeronexus.minio_media_index import media_id
from aeronexus.pv_inspection import (PvConditions, PvInspectionError, PvThresholds, Region,
                                     condition_checks, inspect)
from aeronexus.thermal import thermal_metadata
from aeronexus.thermal_geo import (ThermalGeoIndex, footprint, fov, geometry, ground_sample_m,
                                   optics_for)

from test_thermal import (HEADERS, PREVIEW, THERMAL, rjpeg)
from test_thermal import client, sdk_dir, service  # noqa: F401,F811  (pytest fixtures)


def meta(alt=44.5, pitch=-90.0, yaw=0.0, model="M3T"):
    return {"model": model, "raw_width": 640, "raw_height": 512,
            "position": {"latitude": 49.16, "longitude": 8.59, "relative_altitude_m": alt},
            "gimbal": {"pitch_deg": pitch, "yaw_deg": yaw}, "radiometric": True}


def test_optics_and_fov():
    assert optics_for("M3T")["thermal_dfov_deg"] == 61 and optics_for("m4t")["camera"] == "M4T"
    assert optics_for("Mavic 2") is None and optics_for(None) is None
    h, v = fov(61, 640, 512)
    assert h == pytest.approx(49.4, abs=0.2) and v == pytest.approx(40.4, abs=0.2)
    assert math.hypot(*map(lambda d: math.tan(math.radians(d) / 2), (h, v))) == pytest.approx(
        math.tan(math.radians(30.5)), rel=1e-6)


def test_footprint_nadir_size_orientation_and_gsd():
    corners = footprint(meta(yaw=0))
    (lat_tl, lon_tl), (lat_tr, lon_tr), _, (lat_bl, _) = corners
    width_m = (lon_tr - lon_tl) * 111_320 * math.cos(math.radians(49.16))
    height_m = (lat_tl - lat_bl) * 111_320
    assert width_m == pytest.approx(2 * 44.5 * math.tan(math.radians(fov(61, 640, 512)[0] / 2)), rel=1e-3)
    assert height_m < width_m and lat_tl == pytest.approx(lat_tr)  # north-up for yaw 0
    east = footprint(meta(yaw=90))
    assert east[0][1] > 8.59 and east[0][0] > 49.16  # image top points east
    assert ground_sample_m(meta()) == pytest.approx(width_m / 640, rel=1e-3)
    assert footprint(meta(pitch=-45)) is None and footprint(meta(model="X")) is None
    assert geometry(meta(pitch=-45))["ground_sample_cm"] > geometry(meta())["ground_sample_cm"]
    assert ground_sample_m(meta(pitch=-10)) is None


def test_header_only_metadata_keeps_position():
    data = rjpeg(40, 30, raw=b"\x00\x48" * 1200)
    partial = thermal_metadata(data[:1000], partial=True)  # cut inside the raw data
    assert partial["position"]["latitude"] == pytest.approx(49.160329099)
    assert partial["radiometric"] is None


def test_geo_index_scan_is_incremental_and_prunes(service):
    geo = ThermalGeoIndex(service.index)
    assert geo.map_items()["items"] == []
    first = geo.scan(service.client, "dji-cloud")
    assert (first["indexed"], first["read"], first["failed"]) == (2, 2, 0)
    assert geo.path.stat().st_mode & 0o077 == 0
    items = geo.map_items()["items"]
    assert {i["name"] for i in items} == {"DJI_20241022172329_0438_T.JPG", "DJI_20261002180010_0003_T.JPG"}
    assert all("object_key" not in i and "SERIAL" not in repr(i) for i in items)
    assert geo.scan(service.client, "dji-cloud")["read"] == 0  # unchanged ETags skipped
    del service.client.items[PREVIEW]
    service.index.scan(service.client, "dji-cloud")
    assert geo.scan(service.client, "dji-cloud")["indexed"] == 1


def test_map_api(client, service):
    ThermalGeoIndex(service.index).scan(service.client, "dji-cloud")
    r = client.get("/api/v1/thermal/map", headers=HEADERS)
    assert r.status_code == 200 and len(r.json()["items"]) == 2
    assert client.get("/api/v1/thermal/map").status_code == 401


# ------------------------------------------------------------------ PV ----

def panel_grid(width=40, height=30, base=30.0):
    grid = array("f", [base] * (width * height))
    for x in range(5, 8):           # 3x3 hot cell, +25 K
        for y in range(5, 8):
            grid[y * width + x] = base + 25
    for x in range(20, 32):         # 12x2 warm strip, +12 K
        for y in range(15, 17):
            grid[y * width + x] = base + 12
    grid[25 * width + 35] = base + 6  # single pixel: below min_pixels
    for y in range(height):           # hot road outside the PV area
        grid[y * width + 39] = base + 40
    return width, height, grid


def test_pv_detects_and_classifies_relative_to_median():
    w, h, grid = panel_grid()
    r = inspect(w, h, grid, Region(0, 0, 38, 30), PvThresholds(), ground_sample_m=0.05)
    assert r["reference_c"] == 30.0 and r["anomaly_count"] == 2
    hot, strip = r["anomalies"]
    assert (hot["class"], hot["delta_k"], hot["pixels"], hot["x"], hot["y"]) == (3, 25.0, 9, 5, 5)
    assert (strip["class"], strip["w"], strip["h"]) == (2, 12, 2)
    assert strip["pattern_hint"].startswith("Zellstreifen")
    assert r["class_counts"] == {1: 0, 2: 1, 3: 1} and r["worst_class"] == 3
    assert hot["area_m2"] == pytest.approx(9 * 0.0025)
    assert not r["warnings"]


def test_pv_without_region_counts_road_and_warns():
    w, h, grid = panel_grid()
    r = inspect(w, h, grid, None, PvThresholds(class3_k=30))
    assert r["anomaly_count"] == 3 and any("Gesamtes Bild" in x for x in r["warnings"])
    loose = inspect(w, h, grid, Region(0, 0, 40, 30), PvThresholds(detect_k=0.5, class2_k=1, class3_k=2))
    assert loose["anomaly_count"] >= 3


def test_pv_threshold_and_region_validation():
    with pytest.raises(PvInspectionError):
        PvThresholds(class2_k=20, class3_k=10)
    with pytest.raises(PvInspectionError):
        PvThresholds(detect_k=15)
    with pytest.raises(PvInspectionError):
        PvConditions(cloud_okta=9)
    w, h, grid = panel_grid()
    with pytest.raises(PvInspectionError):
        inspect(w, h, grid, Region(100, 100, 5, 5))


def test_pv_condition_checks():
    checks = {c["id"]: c for c in condition_checks(
        meta(alt=15), PvConditions(irradiance_wm2=550, wind_kmh=30, cloud_okta=1),
        ground_sample_m=ground_sample_m(meta(alt=15)), thresholds=PvThresholds(), emissivity=None)}
    assert checks["irradiance"]["status"] == "fail" and checks["wind"]["status"] == "fail"
    assert checks["clouds"]["status"] == "ok" and checks["view_angle"]["value"] == 0.0
    assert checks["resolution"]["status"] == "ok" and checks["emissivity"]["status"] == "warn"
    tilted = {c["id"]: c for c in condition_checks(
        meta(), PvConditions(module_tilt_deg=35, module_azimuth_deg=180), ground_sample_m=None,
        thresholds=PvThresholds(), emissivity=0.85)}
    assert tilted["view_angle"]["value"] == pytest.approx(35.0) and tilted["view_angle"]["status"] == "warn"
    facing = {c["id"]: c for c in condition_checks(
        meta(pitch=-55, yaw=0), PvConditions(module_tilt_deg=35, module_azimuth_deg=180),
        ground_sample_m=None, thresholds=PvThresholds(), emissivity=0.85)}
    assert facing["view_angle"]["value"] == pytest.approx(0.0, abs=1e-6)
    assert facing["resolution"]["status"] == "unknown"


def test_pv_api(client):
    item = media_id("dji-cloud", THERMAL)
    r = client.get(f"/api/v1/thermal/images/{item}/pv?x=0&y=0&w=4&h=2&detect_k=3&class2_k=5"
                   "&class3_k=6&min_pixels=1&irradiance=700&emissivity=0.85", headers=HEADERS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reference_c"] == 22.5 and body["anomaly_count"] == 1
    assert body["anomalies"][0]["class"] == 1 and body["parameter_overrides"] == {"emissivity": 0.85}
    assert {c["id"] for c in body["checks"]} >= {"irradiance", "wind", "view_angle", "resolution"}
    assert "IEC TS 62446-3" in body["basis"]
    assert client.get(f"/api/v1/thermal/images/{item}/pv?class2_k=30&class3_k=20",
                      headers=HEADERS).status_code == 422
    assert client.get(f"/api/v1/thermal/images/{item}/pv?x=50&y=50&w=5&h=5",
                      headers=HEADERS).status_code == 422
