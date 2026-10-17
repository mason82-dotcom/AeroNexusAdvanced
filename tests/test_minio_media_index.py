"""Offline tests: mocked MinIO pagination, index reconciliation and protected HTTP."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import importlib

import pytest
from fastapi.testclient import TestClient

from aeronexus.minio_media_index import (
    DjiMediaIndex, DjiMediaError, MinioMediaSettings, media_id,
)


TOKEN = "dji-minio-media-library-test-only-token-123456789"
HEADERS = {"Authorization": "Bearer " + TOKEN}
APP_MODULE = importlib.import_module("aeronexus.app")


def obj(name, data=b"\xff\xd8\xfftest", etag="v1"):
    return SimpleNamespace(
        object_name=name, size=len(data), etag=etag,
        last_modified=datetime(2026, 10, 17, tzinfo=timezone.utc),
        is_dir=False,
    )


class FakeResponse:
    def __init__(self, content):
        self.content = content
        self.closed = False
        self.released = False

    def stream(self, n):
        for i in range(0, len(self.content), n):
            yield self.content[i:i + n]

    def close(self):
        self.closed = True

    def release_conn(self):
        self.released = True


class FakeMinio:
    def __init__(self, items=None):
        self.items = items or {}
        self.fail_after = None
        self.reads = 0
        self.streams = []

    def list_objects(self, bucket, recursive):
        assert bucket == "dji-cloud" and recursive is True
        for n, (key, (content, etag)) in enumerate(self.items.items()):
            if self.fail_after is not None and n >= self.fail_after:
                raise RuntimeError("Simulated connection loss")
            yield obj(key, content, etag)

    def stat_object(self, bucket, key):
        self.reads += 1
        content, etag = self.items[key]
        return SimpleNamespace(size=len(content), etag=etag)

    def get_object(self, bucket, key):
        self.reads += 1
        response = FakeResponse(self.items[key][0])
        self.streams.append(response)
        return response


@pytest.fixture
def minio_env(monkeypatch):
    monkeypatch.setenv("AERONEXUS_MINIO_ENDPOINT", "http://127.0.0.1:9000")
    monkeypatch.setenv("AERONEXUS_MINIO_BUCKET", "dji-cloud")
    monkeypatch.setenv("AERONEXUS_MINIO_ACCESS_KEY", "mock-readonly-access")
    monkeypatch.setenv("AERONEXUS_MINIO_SECRET_KEY", "mock-readonly-secret")


def test_idempotent_scan_new_changed_deleted_and_classification(tmp_path):
    index = DjiMediaIndex(tmp_path / "private")
    client = FakeMinio({
        "fly/2026/DJI_0001.JPG": (b"\xff\xd8\xffphoto", "e1"),
        "fly/2026/DJI_0002.DNG": (b"raw", "e2"),
        "fly/2026/DJI_0003.MP4": (b"video", "e3"),
        "ignore/config.json": (b"private", "e4"),
    })
    first = index.scan(client, "dji-cloud")
    assert (first["indexed"], first["added"], first["ignored"]) == (3, 3, 1)
    assert index.path.stat().st_mode & 0o077 == 0
    assert index.root.stat().st_mode & 0o077 == 0
    assert index.list()["total"] == 3
    items = index.list()["media"]
    assert all("object_key" not in m and "bucket" not in m for m in items)
    assert {m["mime"] for m in items} == {
        "image/jpeg", "image/x-adobe-dng", "video/mp4"
    }
    assert any(m["previewable"] for m in items)
    second = index.scan(client, "dji-cloud")
    assert (second["added"], second["updated"], second["unchanged"]) == (0, 0, 3)
    client.items["fly/2026/DJI_0001.JPG"] = (b"\xff\xd8\xffchanged", "e5")
    del client.items["fly/2026/DJI_0002.DNG"]
    client.items["fly/2026/DJI_0004.JPG"] = (b"\xff\xd8\xffnew", "e6")
    third = index.scan(client, "dji-cloud")
    assert (third["added"], third["updated"], third["removed_from_index"]) == (1, 1, 1)
    assert index.get(media_id("dji-cloud", "fly/2026/DJI_0002.DNG")) is None
    assert index.list(query="DJI_0004")["total"] == 1
    assert index.list(query="%")["total"] == 0  # LIKE wildcard escaped
    assert index.list(query="_")["total"] == 3  # literal underscore
    assert index.list(limit=1)["total"] == 3
    assert len(index.list(limit=1)["media"]) == 1
    assert index.get("../bad") is None


def test_interrupted_scan_keeps_last_good_index(tmp_path):
    index = DjiMediaIndex(tmp_path / "private")
    client = FakeMinio({"a.jpg": (b"\xff\xd8\xffone", "1")})
    index.scan(client, "dji-cloud")
    client.items = {"b.jpg": (b"\xff\xd8\xfftwo", "2"),
                    "c.jpg": (b"\xff\xd8\xffthree", "3")}
    client.fail_after = 1
    with pytest.raises(RuntimeError, match="connection loss"):
        index.scan(client, "dji-cloud")
    assert index.list()["total"] == 1
    assert index.get(media_id("dji-cloud", "a.jpg")) is not None
    assert index.get(media_id("dji-cloud", "b.jpg")) is None


def test_settings_reject_plaintext_lan_and_missing_auth(minio_env, monkeypatch):
    good = MinioMediaSettings.from_env()
    assert good.endpoint == "127.0.0.1:9000" and not good.secure
    monkeypatch.setenv("AERONEXUS_MINIO_ENDPOINT", "http://192.168.1.10:9000")
    with pytest.raises(DjiMediaError, match="HTTPS"):
        MinioMediaSettings.from_env()
    monkeypatch.setenv("AERONEXUS_MINIO_ENDPOINT", "https://storage.example:9000")
    assert MinioMediaSettings.from_env().secure
    monkeypatch.delenv("AERONEXUS_MINIO_SECRET_KEY")
    with pytest.raises(DjiMediaError, match="credentials"):
        MinioMediaSettings.from_env()


def test_protected_api_lists_media_and_streams_only_on_demand(
        tmp_path, monkeypatch, minio_env):
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    monkeypatch.setenv("AERONEXUS_WORKSPACE_DIR", str(tmp_path / "workspace"))
    client = FakeMinio({"flights/P_1.JPG": (b"\xff\xd8\xffDJI", "1"),
                        "flights/P_2.DNG": (b"dng-raw", "2")})
    index = DjiMediaIndex(Path(tmp_path) / "workspace")
    index.scan(client, "dji-cloud")
    monkeypatch.setattr(APP_MODULE, "minio_client", lambda settings: client)
    with TestClient(APP_MODULE.app) as api:
        url = "/api/v1/studio/dji-media"
        assert api.get(url).status_code == 401
        listed = api.get(url, headers=HEADERS)
        assert listed.status_code == 200
        assert listed.headers["cache-control"] == "no-store"
        assert listed.json()["total"] == 2
        assert client.reads == 0
        photo_id = media_id("dji-cloud", "flights/P_1.JPG")
        file_path = url + "/" + photo_id + "/file"
        assert api.get(file_path).status_code == 401
        received = api.get(file_path, headers=HEADERS)
        assert received.status_code == 200 and received.content == b"\xff\xd8\xffDJI"
        assert received.headers["x-content-type-options"] == "nosniff"
        assert received.headers["content-type"] == "image/jpeg"
        assert received.headers["cache-control"] == "no-store"
        assert all(r.closed and r.released for r in client.streams)
        raw_id = media_id("dji-cloud", "flights/P_2.DNG")
        raw_path = url + "/" + raw_id + "/file"
        assert api.get(raw_path, headers=HEADERS).status_code == 415
        raw_download = api.get(raw_path + "?download=true", headers=HEADERS)
        assert raw_download.status_code == 200 and raw_download.content == b"dng-raw"
        assert raw_download.headers["content-disposition"] == "attachment"
        assert api.get(url + "/../../../etc/passwd/file", headers=HEADERS).status_code != 200
        assert api.get(url + "/no-such-id/file", headers=HEADERS).status_code == 404
        assert api.post(url, headers=HEADERS).status_code == 405


def test_stale_index_refuses_to_serve_changed_object(tmp_path, monkeypatch, minio_env):
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    monkeypatch.setenv("AERONEXUS_WORKSPACE_DIR", str(tmp_path / "workspace"))
    client = FakeMinio({"a.jpg": (b"\xff\xd8\xffold", "first")})
    DjiMediaIndex(tmp_path / "workspace").scan(client, "dji-cloud")
    client.items["a.jpg"] = (b"\xff\xd8\xffnew", "next")
    monkeypatch.setattr(APP_MODULE, "minio_client", lambda settings: client)
    with TestClient(APP_MODULE.app) as api:
        path = "/api/v1/studio/dji-media/" + media_id("dji-cloud", "a.jpg") + "/file"
        assert api.get(path, headers=HEADERS).status_code == 409
        assert client.streams == []
