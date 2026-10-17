"""Thermal flight analysis: group thermal images into flights and measure a
whole flight with the DJI Thermal SDK in a cancellable background job.

Flights are derived from the private geo index (capture time and position
from the image XMP; ``python -m aeronexus.thermal_geo``). A new flight starts
after a capture gap of more than ``FLIGHT_GAP_MINUTES``. Per-image results
(min/max/mean/median/P95 and hotspot pixel, image-stored measurement
parameters) are persisted in the same private 0600 database and invalidated
when the object's ETag changes. Nothing is written to MinIO or DJI.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
import sqlite3
import threading
import time

from .minio_media_index import DjiMediaError
from .thermal import ThermalError, ThermalNotFound, ThermalService
from .thermal_geo import ThermalGeoIndex
from .thermal_sdk import ThermalSdkError

FLIGHT_GAP_MINUTES = 15
MAX_JOB_IMAGES = 5000
_ID_RE = re.compile(r"[0-9a-f]{64}\Z")


def _when(value: str | None) -> datetime | None:
    try:
        moment = datetime.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None
    if moment is not None and moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def group_flights(rows: list[dict], *, gap_minutes: int = FLIGHT_GAP_MINUTES) -> list[dict]:
    """[{id, start, end, images:[row...]}], newest flight first. ``id`` is the
    opaque id of the flight's first image (stable while no earlier image appears)."""
    timed = sorted(((when, row) for row in rows if (when := _when(row.get("captured_at")))),
                   key=lambda item: (item[0], item[1]["id"]))
    flights: list[dict] = []
    for when, row in timed:
        if not flights or (when - flights[-1]["_end"]).total_seconds() > gap_minutes * 60:
            flights.append({"id": row["id"], "_start": when, "_end": when, "images": []})
        flights[-1]["images"].append(row)
        flights[-1]["_end"] = when
    for flight in flights:
        flight["start"] = flight.pop("_start").isoformat()
        flight["end"] = flight.pop("_end").isoformat()
    return flights[::-1]


class ThermalJobRunning(ThermalError):
    """Only one flight analysis runs at a time (the SDK is single-flight)."""


class ThermalFlights:
    def __init__(self, service: ThermalService):
        self.service = service
        self.geo = ThermalGeoIndex(service.index)
        self._lock = threading.Lock()
        self._job: dict = {"state": "idle"}
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None
        service.stats_sink = self.save_stats

    # ----------------------------------------------------------- storage --
    def save_stats(self, item_id: str, etag: str | None, stats: dict) -> None:
        db = self.geo._connect(write=True)
        try:
            with db:
                db.execute("""INSERT INTO thermal_stats (id, etag, stats, computed_at) VALUES (?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET etag=excluded.etag, stats=excluded.stats,
                    computed_at=excluded.computed_at""",
                           (item_id, etag, json.dumps(stats),
                            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")))
        finally:
            db.close()

    def _rows(self) -> tuple[list[dict], dict[str, tuple[str | None, dict]]]:
        db = self.geo._connect(write=False)
        if db is None:
            return [], {}
        try:
            rows = [dict(r) for r in db.execute(
                "SELECT id, etag, filename, captured_at, model, meta FROM thermal_geo")]
            stats = {}
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='thermal_stats'").fetchone():
                stats = {r["id"]: (r["etag"], json.loads(r["stats"]))
                         for r in db.execute("SELECT id, etag, stats FROM thermal_stats")}
            return rows, stats
        finally:
            db.close()

    @staticmethod
    def _current(row: dict, stats: dict) -> dict | None:
        entry = stats.get(row["id"])
        return entry[1] if entry and entry[0] == row["etag"] else None

    # ------------------------------------------------------------ queries --
    def flights(self) -> dict:
        rows, stats = self._rows()
        out = []
        for flight in group_flights(rows):
            images = flight["images"]
            measured = [s for r in images if (s := self._current(r, stats))]
            hottest = max(measured, key=lambda s: s["max_c"], default=None)
            out.append({
                "id": flight["id"], "start": flight["start"], "end": flight["end"],
                "images": len(images),
                "with_position": sum(1 for r in images if json.loads(r["meta"]).get("position")),
                "analyzed": len(measured),
                "max_c": hottest["max_c"] if hottest else None,
                "model": images[0]["model"],
            })
        return {"flights": out, "gap_minutes": FLIGHT_GAP_MINUTES, "job": self.job()}

    def _flight(self, flight_id: str) -> dict:
        if not isinstance(flight_id, str) or not _ID_RE.fullmatch(flight_id):
            raise ThermalNotFound("Unknown flight")
        rows, stats = self._rows()
        for flight in group_flights(rows):
            if flight["id"] == flight_id:
                return {**flight, "_stats": stats}
        raise ThermalNotFound("Unknown flight")

    def flight_detail(self, flight_id: str, *, limit: int = 200) -> dict:
        flight = self._flight(flight_id)
        ranked, pending = [], 0
        for row in flight["images"]:
            s = self._current(row, flight["_stats"])
            if s is None:
                pending += 1
                continue
            ranked.append({"id": row["id"], "name": row["filename"], "captured_at": row["captured_at"],
                           "max_c": s["max_c"], "min_c": s["min_c"], "median_c": s["median_c"],
                           "p95_c": s["p95_c"], "delta_k": round(s["max_c"] - s["median_c"], 2),
                           "hotspot": s["hotspot"]})
        ranked.sort(key=lambda r: (-r["max_c"], r["id"]))
        return {"id": flight["id"], "start": flight["start"], "end": flight["end"],
                "images": len(flight["images"]), "analyzed": len(ranked), "pending": pending,
                "ranking": ranked[:limit], "job": self.job()}

    def map_items(self) -> dict:
        result = self.geo.map_items()
        rows, stats = self._rows()
        flight_of = {r["id"]: f["id"] for f in group_flights(rows) for r in f["images"]}
        etags = {r["id"]: r["etag"] for r in rows}
        for item in result["items"]:
            entry = stats.get(item["id"])
            s = entry[1] if entry and entry[0] == etags.get(item["id"]) else None
            item["flight_id"] = flight_of.get(item["id"])
            item["stats"] = None if s is None else {
                "max_c": s["max_c"], "median_c": s["median_c"],
                "delta_k": round(s["max_c"] - s["median_c"], 2)}
        return result

    # ---------------------------------------------------------------- job --
    def job(self) -> dict:
        with self._lock:
            return dict(self._job)

    def start(self, flight_id: str) -> dict:
        flight = self._flight(flight_id)
        with self._lock:
            if self._job.get("state") == "running":
                raise ThermalJobRunning("A thermal flight analysis is already running")
            todo = [r for r in flight["images"] if self._current(r, flight["_stats"]) is None]
            self._cancel.clear()
            self._job = {"state": "running", "flight_id": flight_id,
                         "total": min(len(todo), MAX_JOB_IMAGES), "processed": 0,
                         "measured": 0, "failed": 0,
                         "skipped": 0, "already": len(flight["images"]) - len(todo),
                         "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                         "finished_at": None, "seconds": 0.0}
            self._thread = threading.Thread(target=self._run, args=(todo[:MAX_JOB_IMAGES],),
                                            name="thermal-flight-job", daemon=True)
            self._thread.start()
            return dict(self._job)

    def cancel(self) -> dict:
        self._cancel.set()
        return self.job()

    def _run(self, rows: list[dict]) -> None:
        began = time.monotonic()
        state = "done"
        for row in rows:
            if self._cancel.is_set():
                state = "cancelled"
                break
            key = "measured"
            try:
                self.service.measure(row["id"], cache=False)  # stats_sink persists the summary
            except ThermalError:
                key = "skipped"  # not radiometric / no longer indexed
            except (ThermalSdkError, DjiMediaError, OSError, sqlite3.Error):
                key = "failed"
            with self._lock:
                self._job[key] += 1
                self._job["processed"] += 1
                self._job["seconds"] = round(time.monotonic() - began, 1)
        with self._lock:
            self._job["state"] = state
            self._job["seconds"] = round(time.monotonic() - began, 1)
            self._job["finished_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def wait(self, timeout: float | None = None) -> None:
        """For tests and the CLI: block until the current job thread ends."""
        if self._thread is not None:
            self._thread.join(timeout)




def main(argv: list[str] | None = None) -> int:
    """List flights or measure one/all flights (blocking, progress on stderr)."""
    import argparse
    import sys
    from dotenv import load_dotenv
    from .minio_media_index import DjiMediaIndex
    parser = argparse.ArgumentParser(description="Thermal flight analysis with the DJI Thermal SDK")
    parser.add_argument("--env-file", default=".env")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--flight", help="id of the flight to measure (see listing)")
    group.add_argument("--all", action="store_true", help="measure all flights")
    args = parser.parse_args(argv)
    if args.env_file:
        load_dotenv(args.env_file, override=False)
    try:
        flights = ThermalFlights(ThermalService(DjiMediaIndex()))
        listing = flights.flights()["flights"]
        if not args.flight and not args.all:
            for f in listing:
                print(f'{f["id"]}  {f["start"][:16]}  {f["images"]:5d} Bilder  '
                      f'{f["analyzed"]:5d} gemessen  {f["model"] or "-"}')
            return 0
        failed = 0
        for f in listing if args.all else [{"id": args.flight}]:
            flights.start(f["id"])
            while flights.job()["state"] == "running":
                job = flights.job()
                print(f'\r{f["id"][:12]} {job["processed"]}/{job["total"]}', end="", file=sys.stderr)
                flights.wait(2)
            job = flights.job()
            failed += job["failed"]
            print(f'\r{f["id"][:12]} {json.dumps(job)}', file=sys.stderr)
        return 1 if failed else 0
    except ThermalNotFound:
        print("Unknown flight id", file=sys.stderr)
        return 1
    except (ThermalError, DjiMediaError, OSError, sqlite3.Error) as exc:
        print("Thermal flight analysis error: " + str(exc).split("\n", 1)[0], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
