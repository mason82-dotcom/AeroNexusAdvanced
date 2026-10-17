"""Photo catalogue: model/camera classification from DJI metadata, M3E footprints, API."""
import importlib
import math
import struct
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from aeronexus.minio_media_index import DjiMediaIndex, media_id
from aeronexus.photo_catalog import PhotoCatalog, field_of_view, photo_geometry, photo_metadata

from test_thermal import FakeMinio, rjpeg, segment

APP_MODULE = importlib.import_module("aeronexus.app")
TOKEN = "photo-catalog-test-only-dashboard-token-123456"
HEADERS = {"Authorization": "Bearer " + TOKEN}
SERIAL = "1581F6Q8D000TEST"


def exif(f35=24, width=5280, height=3956) -> bytes:
    """Little-endian TIFF: IFD0 -> Exif IFD with 35 mm focal length and pixel size."""
    sub = 26
    ifd0 = struct.pack("<H", 1) + struct.pack("<HHII", 0x8769, 4, 1, sub) + b"\0\0\0\0"
    entries = [(0xA405, 3, 1, f35), (0xA002, 4, 1, width), (0xA003, 4, 1, height)]
    ifd1 = struct.pack("<H", len(entries)) + b"".join(
        struct.pack("<HHI", tag, typ, n) + (struct.pack("<HH", value, 0) if typ == 3
                                            else struct.pack("<I", value))
        for tag, typ, n, value in entries) + b"\0\0\0\0"
    return b"Exif\0\0II*\0" + struct.pack("<I", 8) + ifd0 + ifd1


def photo(model="M3E", camera="WideCamera", *, when="2026-10-04T17:25:00+02:00", alt="+60.000",
          pitch="-90.00", lat="+49.160329099", lon="+8.595456832", f35=24) -> bytes:
    xmp = (f'<x:xmpmeta><rdf:Description tiff:Make="DJI" tiff:Model="{model}" '
           f'xmp:CreateDate="{when}" drone-dji:ImageSource="{camera}" '
           f'drone-dji:GpsStatus="RTK" drone-dji:GpsLatitude="{lat}" drone-dji:GpsLongitude="{lon}" '
           f'drone-dji:AbsoluteAltitude="+170.0" drone-dji:RelativeAltitude="{alt}" '
           f'drone-dji:GimbalPitchDegree="{pitch}" drone-dji:GimbalYawDegree="+0.00" '
           f'drone-dji:DroneSerialNumber="{SERIAL}" drone-dji:NTRIPHost="ntrip.example"/>'
           f'</x:xmpmeta>').encode()
    return b"".join([b"\xff\xd8", segment(0xE1, exif(f35)),
                     segment(0xE1, b"http://ns.adobe.com/xap/1.0/\x00" + xmp),
                     segment(0xC0, struct.pack(">BHHB", 8, 3956, 5280, 3) + b"\0" * 9),
                     segment(0xDA, b"\0" * 10), b"\x00\xff\xd9"])


WIDE_1 = "wayline/DJI_20261004172500_0001_W.JPG"
WIDE_2 = "wayline/DJI_20261004172600_0002_W.JPG"
GROUND = "manual/DJI_20261002164100_0001_W.JPG"
ORG_IR = "fh/org_0b1c2d3e4f.jpg"


@pytest.fixture
def catalog(tmp_path, monkeypatch):
    monkeypatch.setenv("AERONEXUS_WORKSPACE_DIR", str(tmp_path / "workspace"))
    client = FakeMinio({
        WIDE_1: (photo(), "w1"),
        WIDE_2: (photo(when="2026-10-04T17:26:00+02:00", lat="+49.160829099"), "w2"),
        GROUND: (photo(when="2026-10-02T16:41:00+02:00", alt="+1.2", pitch="-10.00"), "g1"),
        ORG_IR: (rjpeg(model="M4T"), "ir"),
        "fh/not_dji.jpg": (b"\xff\xd8\xff\xd9", "x"),
    })
    index = DjiMediaIndex(tmp_path / "workspace")
    index.scan(client, "dji-cloud")
    photos = PhotoCatalog(index)
    photos.client = client
    return photos


def test_metadata_is_whitelisted_and_typed():
    meta = photo_metadata(photo())
    assert (meta["model"], meta["camera"], meta["kind"]) == ("M3E", "WideCamera", "visual")
    assert (meta["width"], meta["height"], meta["focal_length_35mm"]) == (5280, 3956, 24)
    assert meta["position"]["relative_altitude_m"] == 60.0 and meta["gimbal"]["pitch_deg"] == -90
    assert SERIAL not in repr(meta) and "ntrip" not in repr(meta)
    assert photo_metadata(b"\xff\xd8\xff\xd9") is None and photo_metadata(b"PNG") is None
    assert photo_metadata(rjpeg(model="M4T"))["kind"] == "thermal"


def test_m3e_field_of_view_and_ground_sample_distance():
    meta = photo_metadata(photo())
    h, v = field_of_view(meta)
    assert (h, v) == (pytest.approx(71.6, abs=0.1), pytest.approx(56.8, abs=0.1))
    geo = photo_geometry(meta)
    assert len(geo["footprint"]) == 4
    # DJI: GSD (cm/px) of the M3E wide camera = altitude / 36.5
    assert geo["ground_sample_cm"] == pytest.approx(60 / 36.5, rel=0.01)
    oblique = photo_geometry(photo_metadata(photo(pitch="-10.00")))
    assert oblique["footprint"] is None and oblique["ground_sample_cm"] is None
    assert field_of_view({"width": 10, "height": 10}) is None


def test_scan_is_incremental_classifies_and_prunes(catalog):
    assert catalog.summary()["models"] == []
    first = catalog.scan(catalog.client, "dji-cloud")
    assert (first["indexed"], first["read"], first["failed"]) == (4, 5, 0)
    assert catalog.path.stat().st_mode & 0o077 == 0
    summary = catalog.summary()
    assert {m["model"]: m["cameras"] for m in summary["models"]} == {
        "M3E": {"WideCamera": 3}, "M4T": {"InfraredCamera": 1}}
    assert catalog.thermal_ids() == {media_id("dji-cloud", ORG_IR)}
    assert catalog.scan(catalog.client, "dji-cloud")["read"] == 0
    del catalog.client.items[WIDE_2]
    catalog.media.scan(catalog.client, "dji-cloud")
    assert catalog.scan(catalog.client, "dji-cloud")["indexed"] == 3


def test_flights_list_and_map(catalog):
    catalog.scan(catalog.client, "dji-cloud")
    flights = catalog.flights(model="M3E")
    assert [f["images"] for f in flights] == [2, 1]  # newest first, >15 min gap splits
    assert flights[0]["median_altitude_m"] == 60.0
    listing = catalog.list(model="M3E", flight=flights[0]["id"])
    assert listing["total"] == 2 and [i["name"] for i in listing["items"]] == [
        "DJI_20261004172600_0002_W.JPG", "DJI_20261004172500_0001_W.JPG"]
    assert all("object_key" not in i for i in listing["items"])
    full = catalog.map_items(model="M3E")
    assert full["total"] == 3 and sum(1 for i in full["items"] if i["footprint"]) == 2
    assert catalog.map_items(model="M3E", flight=flights[1]["id"])["total"] == 1
    assert catalog.list(model="M3E", camera="ZoomCamera")["total"] == 0
    with pytest.raises(Exception):
        catalog.list(limit=0)


def test_thermal_service_accepts_metadata_thermal_ids(catalog):
    from aeronexus.thermal import ThermalService
    catalog.scan(catalog.client, "dji-cloud")
    service = ThermalService(catalog.media)
    assert service.record(media_id("dji-cloud", ORG_IR))["filename"] == "org_0b1c2d3e4f.jpg"


@pytest.fixture
def client(catalog, monkeypatch):
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    catalog.scan(catalog.client, "dji-cloud")
    return TestClient(APP_MODULE.app)


def test_api_endpoints_and_validation(client):
    for path in ("/api/v1/photos/summary", "/api/v1/photos", "/api/v1/photos/flights",
                 "/api/v1/photos/map"):
        assert client.get(path).status_code == 401
    assert client.get("/api/v1/photos/summary", headers=HEADERS).json()["total"] == 4
    flights = client.get("/api/v1/photos/flights?model=M3E", headers=HEADERS).json()["flights"]
    r = client.get(f"/api/v1/photos?model=M3E&flight={flights[0]['id']}", headers=HEADERS)
    assert r.status_code == 200 and r.json()["total"] == 2
    assert client.get("/api/v1/photos/map?model=M3E", headers=HEADERS).json()["total"] == 3
    for bad in ("model=M3E%27--", "camera=" + "x" * 40, "flight=nothex"):
        assert client.get("/api/v1/photos?" + bad, headers=HEADERS).status_code == 422
    assert client.get("/api/v1/photos/map?flight=abc", headers=HEADERS).status_code == 422


def test_media_page_has_photo_catalogue_and_csp(client):
    r = client.get("/media")
    assert r.status_code == 200 and 'id="photo-catalog"' in r.text
    assert "/api/v1/photos/map" in r.text and "integrity=" in r.text
    csp = r.headers["content-security-policy"]
    assert "connect-src 'self'" in csp and "https://cdn.jsdelivr.net" in csp


def test_large_json_is_compressed_but_media_is_not(client):
    r = client.get("/media", headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("content-encoding") == "gzip"
    from starlette.middleware import gzip
    assert "image/jpeg" in gzip.DEFAULT_EXCLUDED_CONTENT_TYPES


def test_media_sync_runs_photo_catalog_before_thermal_geo(catalog, monkeypatch):
    from aeronexus import media_sync
    order = []
    monkeypatch.setattr(PhotoCatalog, "scan", lambda self, c, b: order.append("photo") or
                        {"indexed": 1, "read": 1, "failed": 0})
    from aeronexus import thermal_geo
    monkeypatch.setattr(thermal_geo.ThermalGeoIndex, "scan", lambda self, c, b: order.append("geo") or
                        {"indexed": 0, "read": 0, "failed": 0})
    sync = media_sync.MediaSync(root=catalog.media.root, client=catalog.client,
                                settings=SimpleNamespace(bucket="dji-cloud"), thermal=False)
    report = sync.run(reason="test")
    assert order == ["photo", "geo"] and report["steps"]["photo_catalog"]["indexed"] == 1
    assert math.isfinite(report["seconds"])


def test_stale_position_is_flagged_not_dropped():
    from aeronexus.photo_catalog import mark_position_outliers
    items = [{"flight": "f", "latitude": 49.16 + i * 1e-4, "longitude": 8.59} for i in range(4)]
    items.append({"flight": "f", "latitude": 35.249, "longitude": 6.159})  # uninitialised fix
    items.append({"flight": "g", "latitude": 35.0, "longitude": 6.0})       # alone: not judged
    assert mark_position_outliers(items) == 1
    assert [i["position_outlier"] for i in items] == [False] * 4 + [True, False]
