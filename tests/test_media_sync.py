"""Automatic catalogue sync after Pilot 2 uploads (fake MinIO, fake DJI Thermal SDK)."""
import importlib
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import aeronexus.media_sync as media_sync
from aeronexus.media_sync import MediaSync, bucket_fingerprint, read_status

from test_thermal import HEADERS, PREVIEW, THERMAL, TOKEN, VISUAL, FakeMinio, rjpeg
from test_thermal import sdk_dir  # noqa: F401  (pytest fixture)


@pytest.fixture
def sync(tmp_path, monkeypatch, sdk_dir):  # noqa: F811
    monkeypatch.setenv("AERONEXUS_WORKSPACE_DIR", str(tmp_path / "ws"))
    client = FakeMinio({THERMAL: (rjpeg(), "e1"), VISUAL: (b"\xff\xd8visual", "e2"),
                        PREVIEW: (rjpeg(raw=b""), "e3")})
    settings = SimpleNamespace(bucket="dji-cloud")
    # Thermal measurements read objects through the default MinIO factories.
    monkeypatch.setattr("aeronexus.minio_media_index.MinioMediaSettings.from_env",
                        classmethod(lambda cls: settings))
    monkeypatch.setattr("aeronexus.minio_media_index.minio_client", lambda s: client)
    return MediaSync(root=tmp_path / "ws", settings=settings, client=client)


def test_fingerprint_changes_on_upload_and_replacement(sync):
    first = bucket_fingerprint(sync.client, "dji-cloud")
    assert first[0] == 3 and bucket_fingerprint(sync.client, "dji-cloud") == first
    sync.client.items["new/DJI_1_0001_T.JPG"] = (rjpeg(), "e9")
    second = bucket_fingerprint(sync.client, "dji-cloud")
    assert second[0] == 4 and second != first
    sync.client.items["new/DJI_1_0001_T.JPG"] = (rjpeg(), "e10")
    assert bucket_fingerprint(sync.client, "dji-cloud") != second


def test_full_pass_updates_all_catalogues_and_status(sync):
    assert read_status(sync.root)["state"] == "not_running"
    report = sync.run(reason="manual")
    steps = report["steps"]
    assert report["ok"] and steps["media_index"]["indexed"] == 3
    assert steps["thermal_geo"]["indexed"] == 2
    assert steps["thermal_measurements"] == {"ok": True, "seconds": steps["thermal_measurements"]["seconds"],
                                             "measured": 1, "failed": 0}
    status = read_status(sync.root)
    assert status["state"] == "idle" and status["runs"] == 1 and status["last_run"]["ok"]
    assert (sync.root / media_sync.STATUS_FILE).stat().st_mode & 0o077 == 0
    again = sync.run(reason="upload")
    assert again["steps"]["thermal_measurements"]["measured"] == 0  # nothing new


def test_failing_step_is_isolated(sync, monkeypatch):
    from aeronexus import thermal_geo
    def boom(*a, **k):
        raise RuntimeError("secret object key in message")
    monkeypatch.setattr(thermal_geo.ThermalGeoIndex, "scan", boom)
    report = sync.run(reason="manual")
    assert report["ok"] is False and report["steps"]["thermal_geo"]["error"] == "RuntimeError"
    assert report["steps"]["media_index"]["ok"] and "secret" not in json.dumps(report)


def test_poll_mode_waits_for_a_finished_upload_burst(sync, monkeypatch):
    sync.thermal = False
    reasons, polls = [], {"n": 0}
    monkeypatch.setattr(sync, "run", lambda reason: reasons.append(reason))

    class Stop(Exception):
        pass

    def fake_sleep(seconds):
        polls["n"] += 1
        n = polls["n"]
        if n == 1:   # upload starts
            sync.client.items["a/DJI_2_0001_T.JPG"] = (rjpeg(), "x1")
        elif n == 2:  # still uploading
            sync.client.items["a/DJI_2_0002_T.JPG"] = (rjpeg(), "x2")
        elif n == 4:
            raise Stop
    monkeypatch.setattr(media_sync.time, "sleep", fake_sleep)
    with pytest.raises(Stop):
        sync._watch_poll(30)
    assert reasons == ["upload"]  # one pass after poll 3 (unchanged since poll 2)
    assert read_status(sync.root)["objects"] == 5


def test_listen_without_permission_falls_back(sync):
    assert sync.listen_allowed(seconds=0.5) is False  # fake client has no event stream


def test_status_api(sync, monkeypatch):
    app = importlib.import_module("aeronexus.app").app
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    client = TestClient(app)
    assert client.get("/api/v1/media/sync").status_code == 401
    assert client.get("/api/v1/media/sync", headers=HEADERS).json() == {"state": "not_running"}
    sync.set(state="idle", mode="poll")
    assert client.get("/api/v1/media/sync", headers=HEADERS).json()["mode"] == "poll"
