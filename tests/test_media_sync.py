"""Automatic catalogue sync after Pilot 2 uploads (fake MinIO, fake DJI Thermal SDK)."""
import importlib
import json
import threading
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from minio.error import S3Error

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
    def run(reason):
        reasons.append(reason)
        return {"ok": True}
    monkeypatch.setattr(sync, "run", run)

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
    assert reasons == ["startup", "upload"]  # one pass after poll 3
    assert read_status(sync.root)["objects"] == 5


@pytest.mark.parametrize("failure", [
    S3Error(response=None, code="AccessDenied", message="private object key",
            resource="private bucket", request_id="r", host_id="h"),
    OSError("private endpoint"),
    None,  # a stream that closes normally must also fall back
])
def test_event_listener_failure_falls_back_without_disclosing_details(sync, monkeypatch, failure):
    @contextmanager
    def listen(*args, **kwargs):
        if failure is not None:
            raise failure
        yield iter(())
    monkeypatch.setattr(sync.client, "listen_bucket_notification", listen, raising=False)
    runs, fallback = [], []
    monkeypatch.setattr(sync, "run", lambda reason: runs.append(reason) or {"ok": True})
    monkeypatch.setattr(sync, "_watch_poll", lambda seconds, **kw: fallback.append((seconds, kw)))
    sync.watch(mode="auto", poll_seconds=30)
    assert runs == ["startup"]
    assert fallback == [(30, {"initial_reason": "listener_fallback"})]
    status = read_status(sync.root)
    assert status["mode"] == "poll"
    assert status["last_listen_error"] == (type(failure).__name__ if failure else "ListenerStopped")
    assert "private" not in json.dumps(status)


@pytest.mark.parametrize("step", ["thermal_geo", "multispectral", "ndvi_summaries", "thermal_measurements"])
def test_returned_failure_counts_make_pass_fail(sync, monkeypatch, step):
    from aeronexus import multispectral, thermal_geo
    if step == "thermal_geo":
        monkeypatch.setattr(thermal_geo.ThermalGeoIndex, "scan",
                            lambda *a: {"indexed": 0, "read": 0, "failed": 7})
    elif step == "multispectral":
        monkeypatch.setattr(multispectral.MultispectralCatalog, "scan",
                            lambda *a: {"captures": 0, "read": 0, "failed": 7})
    elif step == "ndvi_summaries":
        def compute(service):
            service.summary_failures = ["private-capture"] * 7
            return 0
        monkeypatch.setattr(multispectral.MultispectralService, "compute_missing_summaries", compute)
    else:
        monkeypatch.setattr(sync, "_measure_thermal", lambda: {"measured": 0, "failed": 7})
    report = sync.run(reason="manual")
    assert report["ok"] is False and report["steps"][step]["ok"] is False
    assert report["steps"][step]["failed"] == 7
    status = read_status(sync.root)
    assert status["last_error"] and status["last_run"]["ok"] is False
    assert "private-capture" not in json.dumps(report)


def test_once_exits_nonzero_for_partial_failure(sync, monkeypatch, capsys):
    from aeronexus import thermal_geo
    monkeypatch.setattr(media_sync, "MediaSync", lambda **kw: sync)
    monkeypatch.setattr(thermal_geo.ThermalGeoIndex, "scan",
                        lambda *a: {"indexed": 0, "read": 0, "failed": 1})
    assert media_sync.main(["--once", "--env-file", ""]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_poll_detects_upload_during_startup_scan(sync, monkeypatch):
    reasons, polls = [], 0
    def run(reason):
        reasons.append(reason)
        if reason == "startup":
            sync.client.items["new/DJI_3_0001_T.JPG"] = (rjpeg(), "x3")
        return {"ok": True}
    class Stop(Exception):
        pass
    def sleep(seconds):
        nonlocal polls
        polls += 1
        if polls == 3:
            raise Stop
    monkeypatch.setattr(sync, "run", run)
    monkeypatch.setattr(media_sync.time, "sleep", sleep)
    with pytest.raises(Stop):
        sync._watch_poll(30)
    assert reasons == ["startup", "upload"]


def test_failed_pass_retries_without_new_upload(sync, monkeypatch):
    reasons, clock = [], [0.0]
    class Stop(Exception):
        pass
    def run(reason):
        reasons.append(reason)
        return {"ok": len(reasons) > 1}
    def sleep(seconds):
        clock[0] += seconds
        if clock[0] > media_sync.RETRY_SECONDS + seconds:
            raise Stop
    monkeypatch.setattr(sync, "run", run)
    monkeypatch.setattr(media_sync.time, "sleep", sleep)
    monkeypatch.setattr(media_sync.time, "monotonic", lambda: clock[0])
    with pytest.raises(Stop):
        sync._watch_poll(30)
    assert reasons == ["startup", "retry"]


@pytest.mark.parametrize("failed", [False, True])
def test_event_mode_processes_quiet_burst_or_retries_failed_pass(sync, monkeypatch, failed):
    import queue
    reasons, stops, clock = [], [], [0.0]
    listening = threading.Event()
    class Stop(Exception):
        pass
    class Events:
        calls = 0
        def get(self, timeout):
            self.calls += 1
            if self.calls == 1:
                clock[0] = 0.0  # monotonic zero is also a valid event time
                return 0.0
            if self.calls == 2:
                clock[0] = media_sync.RETRY_SECONDS if failed else media_sync.QUIET_SECONDS
                raise queue.Empty
            raise Stop
    def run(reason):
        assert listening.wait(1)
        reasons.append(reason)
        return {"ok": not failed or len(reasons) > 1}
    def listen(events, stop):
        stops.append(stop)
        listening.set()
    monkeypatch.setattr(sync, "run", run)
    monkeypatch.setattr(sync, "_listen", listen)
    monkeypatch.setattr(media_sync.queue, "Queue", Events)
    monkeypatch.setattr(media_sync.time, "monotonic", lambda: clock[0])
    with pytest.raises(Stop):
        sync._watch_events(30)
    assert reasons == ["startup", "retry" if failed else "upload"]
    assert len(stops) == 1 and stops[0].is_set()


def test_status_api(sync, monkeypatch):
    app = importlib.import_module("aeronexus.app").app
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    client = TestClient(app)
    assert client.get("/api/v1/media/sync").status_code == 401
    assert client.get("/api/v1/media/sync", headers=HEADERS).json() == {"state": "not_running"}
    sync.set(state="idle", mode="poll")
    assert client.get("/api/v1/media/sync", headers=HEADERS).json()["mode"] == "poll"
