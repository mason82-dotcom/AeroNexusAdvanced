"""Both media UIs use one private read-only MinIO catalogue."""
import pytest
from fastapi.testclient import TestClient
from aeronexus.app import app
from aeronexus.dji_media_index import browse_media, index_summary
from aeronexus.dji_media_page import render_dji_media_page
from aeronexus.minio_media_index import DjiMediaIndex, DjiMediaError
from test_minio_media_index import FakeMinio, TOKEN, HEADERS


def test_legacy_and_studio_apis_share_catalogue(monkeypatch, tmp_path):
    root = tmp_path / "workspace"
    monkeypatch.setenv("AERONEXUS_WORKSPACE_DIR", str(root))
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    index = DjiMediaIndex(root)
    index.scan(FakeMinio({"folder/A_1.JPG": (b"photo", "1"),
                         "folder/B.DNG": (b"raw", "2"),
                         "folder/C.LRF": (b"video", "3"),
                         "folder/D.WAV": (b"audio", "4")}), "dji-cloud")
    assert index_summary()["kinds"] == {"image": 1, "raw": 1, "video": 1, "audio": 1}
    assert index_summary()["total_bytes"] == 18
    assert browse_media(kind="raw")["items"][0]["name"] == "B.DNG"
    assert browse_media(query="A_")["total"] == 1
    assert browse_media(query="%")["total"] == 0
    with TestClient(app) as api:
        for url in ("/api/v1/dji/media", "/api/v1/dji/media/summary", "/api/v1/studio/dji-media"):
            assert api.get(url).status_code == 401
            response = api.get(url, headers=HEADERS)
            assert response.status_code == 200
            assert response.json()["total"] == 4
            assert "folder/" not in response.text and "object_key" not in response.text
        assert api.get("/api/v1/dji/media?kind=video", headers=HEADERS).json()["total"] == 1
        assert api.get("/media").status_code == 200
    index.scan(FakeMinio({"new.jpg": (b"new", "new")}), "dji-cloud")
    assert browse_media()["total"] == index.list()["total"] == 1


def test_legacy_empty_index_and_invalid_filters(monkeypatch, tmp_path):
    monkeypatch.setenv("AERONEXUS_WORKSPACE_DIR", str(tmp_path / "workspace"))
    assert index_summary()["state"] == browse_media()["state"] == "not_indexed"
    with pytest.raises(DjiMediaError):
        browse_media(kind="invalid")


@pytest.mark.parametrize("url", ["/api/v1/dji/media", "/api/v1/dji/media/summary",
    "/api/v1/studio/dji-media", "/api/v1/studio/dji-media/" + "a"*64 + "/file"])
def test_corrupt_catalogue_is_controlled_and_private(monkeypatch, tmp_path, url):
    root = tmp_path / "workspace"
    monkeypatch.setenv("AERONEXUS_WORKSPACE_DIR", str(root))
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    index = DjiMediaIndex(root)
    index.path.write_bytes(b"not a database: private details")
    index.path.chmod(0o600)
    with TestClient(app) as api:
        response = api.get(url, headers=HEADERS)
    assert response.status_code == 503
    assert "private details" not in response.text and str(root) not in response.text


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


def test_scan_limit_rolls_back_shared_catalogue(tmp_path):
    index = DjiMediaIndex(tmp_path / "workspace")
    index.scan(FakeMinio({"old.jpg": (b"old", "1")}), "dji-cloud")
    before = index.list()
    with pytest.raises(DjiMediaError, match="limit"):
        index.scan(FakeMinio({"a.jpg": (b"a", "2"), "b.jpg": (b"b", "3")}),
                   "dji-cloud", max_objects=1)
    assert index.list() == before


def test_legacy_cli_preserves_dry_run_default(monkeypatch):
    from aeronexus.dji_media_index import main
    calls = []
    monkeypatch.setattr("aeronexus.minio_media_index.main", lambda args: calls.append(args) or 0)
    assert main([]) == 0
    assert "--dry-run" in calls[-1]
    assert main(["--apply", "--max-objects", "100"]) == 0
    assert calls[-1] == ["--max-objects", "100"]
