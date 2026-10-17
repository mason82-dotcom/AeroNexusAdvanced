"""Automatic, read-only catalogue sync after DJI Pilot 2 media uploads.

Pilot 2 uploads land in the MinIO bucket via the local DJI Cloud API server.
This watcher keeps every AeroNexusAdvanced catalogue current:

1. media index (``minio_media_index``)            – full listing, incremental
2. photo catalogue (``photo_catalog``)           – model/camera of every JPEG (M3E, M3T, ...)
3. thermal geo index (``thermal_geo``)            – header range reads of new images
4. multispectral catalogue + NDVI summaries       – header reads, NDVI for new captures
5. thermal flight measurements (optional)         – DJI Thermal SDK for new images

Change detection:
* ``events`` mode when the reader may subscribe to bucket notifications
  (``s3:ListenBucketNotification``, see scripts/pi/grant_minio_listen.py):
  a burst of uploads is processed once it has been quiet for ``QUIET_SECONDS``.
* ``poll`` mode otherwise (no extra MinIO rights): every ``POLL_SECONDS`` a
  listing fingerprint is compared; a changed bucket is processed once two
  polls in a row are identical (the upload burst has finished).
A safety run every ``SAFETY_HOURS`` catches anything missed. Nothing is ever
written to MinIO or DJI; only the private 0600 catalogues and a status file.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import queue
import sqlite3
import sys
import threading
import time

from .minio_media_index import DjiMediaError, DjiMediaIndex, MinioMediaSettings, minio_client

LOG = logging.getLogger("aeronexus.media_sync")
STATUS_FILE = "media_sync_status.json"
POLL_SECONDS = 120
QUIET_SECONDS = 45
MAX_DELAY_SECONDS = 600
SAFETY_HOURS = 6
RETRY_SECONDS = 120


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def bucket_fingerprint(client, bucket: str) -> tuple[int, str]:
    """(object count, digest of key/etag/size) – changes on any upload or removal."""
    digest, count = hashlib.sha256(), 0
    for obj in client.list_objects(bucket, recursive=True):
        count += 1
        digest.update(f"{obj.object_name}\0{obj.etag}\0{obj.size}\n".encode("utf-8", "replace"))
    return count, digest.hexdigest()


def read_status(root: Path) -> dict:
    path = root / STATUS_FILE
    try:
        if path.is_symlink() or not path.is_file():
            return {"state": "not_running"}
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"state": "unreadable"}


class MediaSync:
    def __init__(self, *, root: Path | None = None, thermal: bool = True,
                 settings: MinioMediaSettings | None = None, client=None):
        self.index = DjiMediaIndex(root)
        self.root = self.index.root
        self.settings = settings or MinioMediaSettings.from_env()
        self.client = client or minio_client(self.settings)
        self.thermal = thermal
        self.status: dict = {"state": "starting", "mode": None, "runs": 0, "last_run": None,
                             "last_change_at": None, "last_error": None}

    # ---------------------------------------------------------- status --
    def _save_status(self) -> None:
        path = self.root / STATUS_FILE
        tmp = path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(self.status, handle, ensure_ascii=False)
        os.replace(tmp, path)

    def set(self, **values) -> None:
        self.status.update(values)
        try:
            self._save_status()
        except OSError:
            LOG.warning("media sync status could not be written")

    # -------------------------------------------------------- pipeline --
    def run(self, *, reason: str) -> dict:
        """One catalogue pass. Each step is isolated; one failure does not stop the rest."""
        from .multispectral import MultispectralCatalog, MultispectralService
        from .photo_catalog import PhotoCatalog
        from .thermal_geo import ThermalGeoIndex
        started = time.monotonic()
        self.set(state="running", current_reason=reason, run_started_at=_now())
        report: dict = {"reason": reason, "started_at": _now(), "steps": {}}

        def step(name, func):
            began = time.monotonic()
            try:
                result = func()
                values = result if isinstance(result, dict) else {"result": result}
                report["steps"][name] = {**values, "ok": not values.get("failed", 0),
                                         "seconds": round(time.monotonic() - began, 1)}
            except Exception as exc:  # report the type only: SDK/MinIO texts may echo keys
                report["steps"][name] = {"ok": False, "error": type(exc).__name__,
                                         "seconds": round(time.monotonic() - began, 1)}
                LOG.warning("media sync step %s failed: %s", name, type(exc).__name__)

        bucket = self.settings.bucket
        step("media_index", lambda: _pick(self.index.scan(self.client, bucket),
                                          "indexed", "added", "updated", "removed_from_index"))
        # Before thermal_geo: FlightHub IR uploads (org_*.jpg) are recognised by metadata.
        step("photo_catalog", lambda: _pick(PhotoCatalog(self.index).scan(self.client, bucket),
                                            "indexed", "read", "failed"))
        step("thermal_geo", lambda: _pick(ThermalGeoIndex(self.index).scan(self.client, bucket),
                                          "indexed", "read", "failed"))
        step("multispectral", lambda: _pick(MultispectralCatalog(self.index).scan(self.client, bucket),
                                            "captures", "read", "failed"))

        def ndvi_summaries():
            service = MultispectralService(self.index)
            computed = service.compute_missing_summaries()
            return {"computed": computed, "failed": len(service.summary_failures)}

        step("ndvi_summaries", ndvi_summaries)
        if self.thermal:
            step("thermal_measurements", self._measure_thermal)
        report["seconds"] = round(time.monotonic() - started, 1)
        report["finished_at"] = _now()
        report["ok"] = all(s["ok"] for s in report["steps"].values())
        self.set(state="idle", last_run=report, runs=self.status.get("runs", 0) + 1,
                 current_reason=None,
                 last_error=None if report["ok"] else report["finished_at"])
        LOG.info("media sync (%s) finished in %.1f s, ok=%s", reason, report["seconds"], report["ok"])
        return report

    def _measure_thermal(self) -> dict:
        """Measure every not yet measured thermal image (all flights, oldest first)."""
        from .thermal import ThermalService
        from .thermal_flights import ThermalFlights
        from .thermal_sdk import ThermalSdkUnavailable
        flights = ThermalFlights(ThermalService(self.index))
        try:
            flights.service.sdk()
        except ThermalSdkUnavailable:
            return {"skipped": "DJI Thermal SDK not configured"}
        measured = failed = 0
        for flight in reversed(flights.flights()["flights"]):
            if flight["analyzed"] >= flight["images"]:
                continue
            job = flights.start(flight["id"])
            if not job.get("total"):
                continue
            flights.wait()
            job = flights.job()
            measured += job["measured"]
            failed += job["failed"]
        return {"measured": measured, "failed": failed}

    # ---------------------------------------------------------- watcher --
    def _listen(self, events: queue.Queue, stop: threading.Event) -> None:
        try:
            with self.client.listen_bucket_notification(
                    self.settings.bucket,
                    events=["s3:ObjectCreated:*", "s3:ObjectRemoved:*"]) as stream:
                for _ in stream:
                    if stop.is_set():
                        return
                    events.put(time.monotonic())
        except Exception as exc:
            # MinIO reports permission codes on S3Error, not in the class name.
            # Any broken listener falls back to polling; never inspect or expose
            # exception text, which may contain private keys or URLs.
            events.put(("error", type(exc).__name__))
        else:
            if not stop.is_set():
                events.put(("error", "ListenerStopped"))

    def watch(self, *, mode: str = "auto", poll_seconds: int = POLL_SECONDS) -> None:
        if mode == "auto":
            mode = "events"
        self.set(mode=mode)
        LOG.info("media sync watching bucket in %s mode", mode)
        if mode == "events":
            self._watch_events(poll_seconds)
        else:
            self._watch_poll(poll_seconds)

    def _safety_due(self, last: float) -> bool:
        return time.monotonic() - last >= SAFETY_HOURS * 3600

    def _watch_poll(self, poll_seconds: int, *, initial_reason: str = "startup") -> None:
        # Take the baseline BEFORE the scan, so uploads during the scan are
        # detected on the next poll rather than silently accepted as indexed.
        indexed = previous = bucket_fingerprint(self.client, self.settings.bucket)
        report = self.run(reason=initial_reason)
        last_run = time.monotonic()
        retry_at = None if report["ok"] else last_run + RETRY_SECONDS
        changed_since = None
        while True:
            time.sleep(poll_seconds)
            try:
                current = bucket_fingerprint(self.client, self.settings.bucket)
            except Exception as exc:
                self.set(last_poll_error=type(exc).__name__, last_poll_at=_now())
                continue
            self.set(last_poll_at=_now(), objects=current[0])
            if current != indexed and current != previous:
                if changed_since is None:
                    changed_since = time.monotonic()
                self.set(last_change_at=_now(), state="upload_in_progress")
            stable = current != indexed and current == previous  # the burst has finished
            overdue = changed_since is not None and time.monotonic() - changed_since >= MAX_DELAY_SECONDS
            retry_due = retry_at is not None and time.monotonic() >= retry_at
            # A failed pass has its own retry deadline; a stable fingerprint
            # must not cause a retry on every poll or postpone it for six hours.
            if ((stable and retry_at is None) or (overdue and current != indexed)
                    or retry_due):
                report = self.run(reason="retry" if retry_due else "upload")
                indexed, last_run, changed_since = current, time.monotonic(), None
                retry_at = None if report["ok"] else last_run + RETRY_SECONDS
            elif self._safety_due(last_run):
                report = self.run(reason="safety")
                indexed, last_run = current, time.monotonic()
                retry_at = None if report["ok"] else last_run + RETRY_SECONDS
            previous = current

    def _watch_events(self, poll_seconds: int) -> None:
        events: queue.Queue = queue.Queue()
        stop = threading.Event()
        threading.Thread(target=self._listen, args=(events, stop), daemon=True).start()
        try:
            self._consume_events(events, stop, poll_seconds)
        finally:
            stop.set()

    def _consume_events(self, events: queue.Queue, stop: threading.Event, poll_seconds: int) -> None:
        first = last = None
        report = self.run(reason="startup")
        last_run = time.monotonic()
        retry_at = None if report["ok"] else last_run + RETRY_SECONDS
        while True:
            try:
                item = events.get(timeout=5)
                if isinstance(item, tuple):
                    self.set(last_listen_error=item[1])
                    stop.set()
                    self.set(mode="poll")
                    return self._watch_poll(poll_seconds, initial_reason="listener_fallback")
                if first is None:
                    first = item
                last = item
                self.set(last_change_at=_now(), state="upload_in_progress")
            except queue.Empty:
                pass
            now = time.monotonic()
            retry_due = retry_at is not None and now >= retry_at
            if ((last is not None and (now - last >= QUIET_SECONDS or now - first >= MAX_DELAY_SECONDS))
                    or retry_due):
                report = self.run(reason="retry" if retry_due else "upload")
                first = last = None
                last_run = time.monotonic()
                retry_at = None if report["ok"] else last_run + RETRY_SECONDS
            elif self._safety_due(last_run):
                report = self.run(reason="safety")
                last_run = time.monotonic()
                retry_at = None if report["ok"] else last_run + RETRY_SECONDS


def _pick(report: dict, *keys: str) -> dict:
    return {k: report.get(k) for k in keys}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only catalogue sync after Pilot 2 uploads")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--once", action="store_true", help="one complete pass, then exit")
    parser.add_argument("--mode", choices=("auto", "events", "poll"), default="auto")
    parser.add_argument("--poll-seconds", type=int, default=POLL_SECONDS)
    parser.add_argument("--no-thermal", action="store_true",
                        help="skip DJI Thermal SDK measurements of new thermal images")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if not 30 <= args.poll_seconds <= 3600:
        parser.error("--poll-seconds must be between 30 and 3600")
    try:
        from dotenv import load_dotenv
        if args.env_file:
            load_dotenv(args.env_file, override=False)
        thermal = not args.no_thermal and os.environ.get("AERONEXUS_MEDIA_SYNC_THERMAL", "1") != "0"
        sync = MediaSync(thermal=thermal)
        if args.once:
            report = sync.run(reason="manual")
            print(json.dumps(report, ensure_ascii=False))
            return 0 if report["ok"] else 1
        sync.watch(mode=args.mode, poll_seconds=args.poll_seconds)
        return 0
    except (DjiMediaError, OSError, sqlite3.Error) as exc:
        print("Media sync error: " + str(exc).split("\n", 1)[0], file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
