"""Read-only originals, bounded export storage and authenticated package APIs."""
import json
import os
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

from fastapi.testclient import TestClient
import pytest

from aeronexus import metashape_bridge as bridge
from aeronexus.metashape_worker import validate_job
from aeronexus.minio_media_index import DjiMediaChanged, DjiMediaIndex
from aeronexus.multispectral import MultispectralService
from test_multispectral import APP_MODULE, HEADERS, TOKEN, FakeMinio, SERIAL, band, rgb_jpeg


CAPTURES = [str(i) * 32 for i in (1, 2, 3)]


@pytest.fixture
def ortho(tmp_path, monkeypatch):
    monkeypatch.setenv("AERONEXUS_WORKSPACE_DIR", str(tmp_path / "ws"))
    items = {}
    for uuid in CAPTURES:
        for name in ("Green", "Red", "RedEdge", "NIR"):
            items[f"private-flight/{uuid}_{name}.tif"] = (band(20000, band=name, uuid=uuid), name)
        items[f"private-flight/{uuid}_D.JPG"] = (rgb_jpeg(uuid), "rgb")
    client = FakeMinio(items)
    index = DjiMediaIndex(tmp_path / "ws")
    index.scan(client, "dji-cloud")
    service = MultispectralService(index, settings_factory=lambda: SimpleNamespace(bucket="dji-cloud"),
                                   client_factory=lambda settings: client)
    service.catalog.scan(client, "dji-cloud")
    service.client = client
    return service


@pytest.fixture
def ortho_api(ortho, monkeypatch):
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    monkeypatch.setattr(APP_MODULE.app.state, "ms_service", ortho, raising=False)
    return TestClient(APP_MODULE.app)


@pytest.mark.parametrize("mode,count", [("rgb", 3), ("multispectral", 12)])
def test_package_copies_raw_originals_and_bundles_independent_worker(ortho, tmp_path, mode, count):
    originals = dict(ortho.client.items)
    info = bridge.prepare_package(ortho, CAPTURES, mode)
    archive = bridge.package_path(ortho, info["id"])
    assert archive.stat().st_mode & 0o077 == 0
    assert archive.parent.stat().st_mode & 0o077 == 0
    assert info["files"] == count
    with ZipFile(archive) as z:
        manifest = json.loads(z.read("manifest.json"))
        assert len(manifest["files"]) == count
        assert "private-flight" not in repr(manifest) and SERIAL not in repr(manifest)
        assert all(not n.startswith("/") and ".." not in n.split("/") for n in z.namelist())
        assert b"GeoSense" in z.read("worker.py") and "README.txt" in z.namelist()
        for record in manifest["files"]:
            assert z.read(record["path"]) in [v[0] for v in originals.values()]
        extracted = tmp_path / "extracted"
        z.extractall(extracted)
    assert validate_job(extracted)["mode"] == mode
    assert ortho.client.items == originals


@pytest.mark.parametrize("captures", [[], CAPTURES[:2], [CAPTURES[0]] * 3,
                                      ["../escape"] * 3, CAPTURES + ["4" * 32] * 100])
def test_invalid_selection_is_rejected(ortho, captures):
    with pytest.raises(bridge.MetashapeExportError):
        bridge.prepare_package(ortho, captures, "rgb")


def test_changed_etag_fails_and_removes_partial_archive(ortho):
    key = f"private-flight/{CAPTURES[0]}_D.JPG"
    data, _ = ortho.client.items[key]
    ortho.client.items[key] = (data, "new-etag")
    with pytest.raises(DjiMediaChanged):
        bridge.prepare_package(ortho, CAPTURES, "rgb")
    assert list((ortho.media.root / "metashape_exports").iterdir()) == []


def test_mismatched_capture_metadata_is_rejected(ortho):
    key = f"private-flight/{CAPTURES[0]}_D.JPG"
    data, etag = ortho.client.items[key]
    ortho.client.items[key] = (data.replace(CAPTURES[0].encode(), CAPTURES[1].encode()), etag)
    with pytest.raises(DjiMediaChanged):
        bridge.prepare_package(ortho, CAPTURES, "rgb")


def test_missing_rgb_is_not_silently_replaced_with_preview(ortho):
    del ortho.client.items[f"private-flight/{CAPTURES[0]}_D.JPG"]
    ortho.media.scan(ortho.client, "dji-cloud")
    ortho.catalog.scan(ortho.client, "dji-cloud")
    with pytest.raises(bridge.MetashapeExportError, match="RGB"):
        bridge.prepare_package(ortho, CAPTURES, "rgb")


def test_export_limits_disk_and_concurrent_work(ortho, monkeypatch):
    with monkeypatch.context() as mp:
        mp.setattr(bridge.shutil, "disk_usage", lambda p: SimpleNamespace(free=0))
        with pytest.raises(bridge.MetashapeExportError, match="disk space"):
            bridge.prepare_package(ortho, CAPTURES, "rgb")
    bridge._EXPORT_LOCK.acquire()
    try:
        with pytest.raises(bridge.MetashapeExportBusy):
            bridge.prepare_package(ortho, CAPTURES, "rgb")
    finally:
        bridge._EXPORT_LOCK.release()


def test_package_quota_expiry_and_deletion(ortho, monkeypatch):
    monkeypatch.setattr(bridge, "MAX_PACKAGES", 1)
    first = bridge.prepare_package(ortho, CAPTURES, "rgb")
    with pytest.raises(bridge.MetashapeExportError, match="packages"):
        bridge.prepare_package(ortho, CAPTURES, "rgb")
    path = bridge.package_path(ortho, first["id"])
    os.utime(path.parent, (1, 1))
    with pytest.raises(bridge.MetashapePackageNotFound):
        bridge.package_path(ortho, first["id"])
    second = bridge.prepare_package(ortho, CAPTURES, "rgb")
    assert not path.parent.exists()
    bridge.remove_package(ortho, second["id"])
    assert bridge.list_packages(ortho) == []


def test_symlinked_package_and_path_traversal_are_refused(ortho, tmp_path):
    root = bridge._root(ortho)
    (root / ("f" * 32)).symlink_to(tmp_path, target_is_directory=True)
    for value in ("f" * 32, "../outside", "nope"):
        with pytest.raises(bridge.MetashapePackageNotFound):
            bridge.package_path(ortho, value)
        with pytest.raises(bridge.MetashapePackageNotFound):
            bridge.remove_package(ortho, value)


def test_authenticated_api_prepare_download_delete(ortho_api, ortho):
    base = "/api/v1/multispectral/metashape/packages"
    assert ortho_api.get(base).status_code == 401
    assert ortho_api.post(base, json={"capture_uuids": CAPTURES}).status_code == 401
    response = ortho_api.post(base, headers=HEADERS, json={"capture_uuids": CAPTURES, "mode": "rgb"})
    assert response.status_code == 201
    info = response.json()
    assert "private-flight" not in repr(info) and str(ortho.media.root) not in repr(info)
    assert ortho_api.get(info["download_url"]).status_code == 401
    result = ortho_api.get(info["download_url"], headers=HEADERS)
    assert result.status_code == 200 and result.content.startswith(b"PK")
    assert result.headers["cache-control"] == "no-store"
    assert ortho_api.get(base, headers=HEADERS).json()["packages"][0]["id"] == info["id"]
    assert ortho_api.delete(base + "/" + info["id"]).status_code == 401
    assert ortho_api.delete(base + "/" + info["id"], headers=HEADERS).status_code == 204
    assert ortho_api.get(info["download_url"], headers=HEADERS).status_code == 404


def test_api_rejects_paths_and_unknown_fields(ortho_api):
    base = "/api/v1/multispectral/metashape/packages"
    for body in ({"capture_uuids": CAPTURES, "output_path": "/etc"},
                 {"capture_uuids": CAPTURES, "mode": "thermal"},
                 {"capture_uuids": CAPTURES[:2]}):
        assert ortho_api.post(base, headers=HEADERS, json=body).status_code == 422
