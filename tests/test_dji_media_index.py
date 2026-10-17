"""Phase 20: DJI MinIO inventory remains read-only and private."""
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from aeronexus.app import app
from aeronexus.dji_media_index import (
    MediaIndexError, browse_media, bucket_from_cloud_env, classify,
    index_entries, index_summary, media_row,
)
from aeronexus.dji_media_page import render_dji_media_page

BUCKET = "dji-media"
TOKEN = "phase20-dashboard-token-with-sufficient-length-2026"


def obj(name, size=100, modified="2026-10-17T00:01:02Z", etag="aaa"):
    return {"status": "success", "type": "file", "key": name,
            "size": size, "lastModified": modified, "etag": etag}


def test_minio_bucket_read_without_evaluating_shell_or_exposing_secrets(tmp_path):
    env = tmp_path / ".env"
    env.write_text("MINIO_ROOT_PASSWORD=secret\nMINIO_BUCKET=dji-media\n"
                   "DJI_APP_KEY=not-for-indexer\n")
    assert bucket_from_cloud_env(env) == BUCKET
    env.write_text("MINIO_BUCKET=$(touch /tmp/should-not-run)\n")
    with pytest.raises(MediaIndexError):
        bucket_from_cloud_env(env)


@pytest.mark.parametrize(("key", "kind"), [
    ("flight/DCIM/DJI_0001.JPG", "image"),
    ("thermal/IMG_0002.TIFF", "image"),
    ("flight/IMG_0003.DNG", "raw"),
    ("clip.MP4", "video"),
    ("clip.LRF", "video"),
    ("track.SRT", "sidecar"),
    ("audio.WAV", "audio"),
])
def test_types_are_based_on_file_extension_only(key, kind):
    assert classify(key)[0] == kind


def test_unrecognized_and_unsafe_names_not_indexed():
    for key in ("", "folder/", "file.exe", "file.db", "x" * 4097,
                "\x00.jpg", None):
        assert classify(key) is None


def test_media_entry_is_whitelisted_and_stable():
    entry = obj("DCIM/DJI_0001.JPG")
    entry["credentials"] = "must-never-be-indexed"
    a = media_row(entry, BUCKET)
    b = media_row(entry, BUCKET)
    assert a == b
    assert a["kind"] == "image"
    assert len(a["id"]) == 64
    assert "credentials" not in a
    assert "DCIM/" in a["object_key"]
    with pytest.raises(MediaIndexError):
        media_row({"status": "error", "message": "secret"}, BUCKET)


def test_dry_run_does_not_create_database(tmp_path):
    db = tmp_path / "private" / "index.sqlite3"
    result = index_entries([obj("a.jpg"), obj("a.txt")], BUCKET, db, dry_run=True)
    assert result["seen"] == 2 and result["media"] == 1
    assert result["dry_run"] is True
    assert not db.exists()
    assert index_summary(db)["state"] == "not_indexed"


def test_apply_index_is_idempotent_and_current_scan_filters_missing(tmp_path):
    db = tmp_path / "private" / "index.sqlite3"
    scan1 = [obj("DCIM/A.JPG", 101), obj("DCIM/B.DNG", 202),
             obj("DCIM/C.MP4", 303), obj("no.txt")]
    first = index_entries(scan1, BUCKET, db)
    assert first["new"] == 3
    assert index_summary(db)["total"] == 3
    assert index_summary(db)["total_bytes"] == 606
    assert db.stat().st_mode & 0o777 == 0o600
    assert db.parent.stat().st_mode & 0o777 == 0o700

    same = index_entries(scan1, BUCKET, db)
    assert same["new"] == 0 and same["unchanged"] == 3
    changed = index_entries([obj("DCIM/A.JPG", 111, etag="new")], BUCKET, db)
    assert changed["updated"] == 1
    summary = index_summary(db)
    assert summary["total"] == 1
    assert summary["total_bytes"] == 111
    assert browse_media(db)["items"][0]["name"] == "A.JPG"
    assert "object_key" not in browse_media(db)["items"][0]
    # Previously indexed originals are not deleted even when absent in a scan.
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM media").fetchone()[0] == 3


def test_listing_failure_rolls_back_entire_scan(tmp_path):
    db = tmp_path / "data.sqlite3"
    index_entries([obj("one.jpg")], BUCKET, db)
    initial = index_summary(db)

    def fails_after_one():
        yield obj("new.jpg")
        raise MediaIndexError("Simulated listing failure")

    with pytest.raises(MediaIndexError):
        index_entries(fails_after_one(), BUCKET, db)
    assert index_summary(db) == initial
    assert browse_media(db)["items"][0]["name"] == "one.jpg"


def test_excessive_listing_rolls_back(tmp_path):
    db = tmp_path / "data.sqlite3"
    index_entries([obj("one.jpg")], BUCKET, db)
    with pytest.raises(MediaIndexError, match="Scan-Limit"):
        index_entries([obj("other.jpg"), obj("third.jpg")], BUCKET,
                      db, max_objects=1)
    assert index_summary(db)["total"] == 1


def test_safe_search_and_pagination(tmp_path):
    db = tmp_path / "data.sqlite3"
    index_entries([obj("A_1.JPG"), obj("A%2.MP4"),
                   obj("another.DNG"), obj("a' OR 1=1 --.JPG")], BUCKET, db)
    result = browse_media(db, query="A_", limit=1)
    assert result["total"] == 1
    assert result["items"][0]["name"] == "A_1.JPG"
    assert browse_media(db, query="A%")["total"] == 1
    assert browse_media(db, query="' OR 1=1")["total"] == 1
    assert browse_media(db, kind="video")["total"] == 1
    assert browse_media(db, kind="video", offset=1)["items"] == []
    with pytest.raises(MediaIndexError):
        browse_media(db, kind="unknown")
    with pytest.raises(MediaIndexError):
        browse_media(db, query="A" * 201)


def test_media_api_has_access_controls_no_storage_secrets(monkeypatch, tmp_path):
    db = tmp_path / "index.sqlite3"
    index_entries([obj("folder/private-name.JPG")], BUCKET, db)
    monkeypatch.setattr("aeronexus.dji_media_index.DEFAULT_DATABASE", db)
    # Default argument captures the original constant, so substitute the API
    # functions at their import site and verify the actual access policy.
    import aeronexus.app as unused  # avoid module shadowing in test environment
    import importlib
    application_module = importlib.import_module("aeronexus.app")
    monkeypatch.setattr(application_module, "index_summary", lambda: index_summary(db))
    monkeypatch.setattr(application_module, "browse_media",
                        lambda **kw: browse_media(db, **kw))
    monkeypatch.delenv("AERONEXUS_STATUS_TOKEN", raising=False)
    with TestClient(app) as client:
        assert client.get("/api/v1/dji/media").status_code == 503
        assert client.get("/api/v1/dji/media/summary").status_code == 503
        monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
        assert client.get("/api/v1/dji/media").status_code == 401
        headers = {"Authorization": "Bearer " + TOKEN}
        listed = client.get("/api/v1/dji/media", headers=headers)
        assert listed.status_code == 200
        assert listed.json()["total"] == 1
        assert listed.json()["items"][0]["name"] == "private-name.JPG"
        assert "folder/" not in listed.text
        assert "MINIO_ROOT_PASSWORD" not in listed.text
        assert "object_key" not in listed.text
        assert client.get("/api/v1/dji/media/summary", headers=headers).json()["total"] == 1
        assert client.get("/api/v1/dji/media?kind=invalid",
                          headers=headers).status_code == 422
        assert client.post("/api/v1/dji/media", headers=headers).status_code == 405
        shell = client.get("/media")
        assert shell.status_code == 200
        assert shell.headers["x-frame-options"] == "DENY"
        assert "frame-ancestors 'none'" in shell.headers["content-security-policy"]
        assert TOKEN not in shell.text


def test_static_media_page_never_inserts_dynamic_html_or_downloads():
    html = render_dji_media_page()
    assert "DJI-MinIO-Medienindex" in html
    assert 'getJSON("/api/v1/dji/media/summary")' in html
    assert 'fetch(url,{cache:"no-store"})' in html
    assert "textContent=String(value??" in html
    assert "innerHTML" not in html
    assert "localStorage" not in html
    assert "presigned" not in html
    assert "method:\"POST\"" not in html
    assert "window.setInterval(refresh,60000)" in html
