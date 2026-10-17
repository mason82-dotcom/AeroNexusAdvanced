"""DJI photo catalogue: every JPEG in the read-only MinIO index classified by
aircraft model and camera from its own metadata (not the file name).

Covers Mavic 3 Enterprise (M3E), Mavic 3 Thermal (M3T), Matrice 4T (M4T) and
Mavic 3 Multispectral (M3M) photos, including FlightHub uploads named
``org_*.jpg``. Per image: model, camera (``ImageSource``: WideCamera,
ZoomCamera, InfraredCamera, MS_CAMERA, ...), capture time, position, relative
altitude, gimbal angles and the EXIF 35 mm equivalent focal length. The field
of view follows from the focal length (36x24 mm diagonal 43.27 mm), so
footprints and ground sample distance work for any camera without a spec
table. A scan range-reads only the first 256 KiB per object, is incremental
by ETag and never writes to MinIO. Serial numbers and NTRIP data are not stored.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
import os
import re
import sqlite3
import sys

from .minio_media_index import DjiMediaError, DjiMediaIndex
from .thermal import ThermalError, _num, _text, _xmp_fields, exif_fields, jpeg_segments
from .thermal_geo import ground_footprint

DB_NAME = "photo_catalog.sqlite3"
META_VERSION = "1"
HEADER_BYTES = 256 * 1024
FULL_FRAME_DIAGONAL_MM = 43.2666
OUTLIER_KM = 20.0  # from the flight's median position
MODEL_NAMES = {"M3E": "Mavic 3 Enterprise", "M3T": "Mavic 3 Thermal", "M3M": "Mavic 3 Multispectral",
               "M4T": "Matrice 4T", "M4E": "Matrice 4E", "M30T": "Matrice 30T", "M30": "Matrice 30"}
CAMERA_NAMES = {"WideCamera": "Weitwinkel", "ZoomCamera": "Zoom/Tele", "InfraredCamera": "Infrarot",
                "MS_CAMERA": "Multispektral (Vorschau)", "VisibleCamera": "RGB"}
_SAFE = re.compile(r"[A-Za-z0-9_ .:+-]{1,40}\Z")


def kind_of(camera: str | None) -> str:
    if camera == "InfraredCamera":
        return "thermal"
    if camera and camera.upper().startswith("MS"):
        return "multispectral"
    return "visual"


def photo_metadata(head: bytes) -> dict | None:
    """Whitelisted catalogue entry from the first bytes of a DJI JPEG."""
    try:
        seg = jpeg_segments(head, partial=True)
    except ThermalError:
        return None
    x = _xmp_fields(seg["xmp"])
    d = lambda name: x.get("drone-dji:" + name)  # noqa: E731
    model = _text(x.get("tiff:Model") or d("DroneModel"), 24)
    if not model or x.get("tiff:Make", "DJI") != "DJI":
        return None
    exif = exif_fields(seg["exif"])
    lat = _num(d("GpsLatitude"), -90, 90)
    lon = _num(d("GpsLongitude") or d("GpsLongtitude"), -180, 180)
    if lat is None or lon is None or (abs(lat) < 1e-4 and abs(lon) < 1e-4):
        lat = lon = None
    camera = _text(d("ImageSource"), 32) or ("VisibleCamera" if model.upper().startswith("M3M") else None)
    f35 = exif.get("focal_length_35mm")
    width, height = exif.get("pixel_width"), exif.get("pixel_height")
    if not (isinstance(width, int) and isinstance(height, int)) and seg["size"]:
        width, height = seg["size"]
    captured = _text(x.get("xmp:CreateDate"), 40)
    if not captured and isinstance(exif.get("date_time_original"), str):
        captured = exif["date_time_original"].replace(":", "-", 2).replace(" ", "T")
    return {
        "model": model if _SAFE.fullmatch(model) else None,
        "camera": camera if camera and _SAFE.fullmatch(camera) else None,
        "kind": kind_of(camera),
        "captured_at": captured,
        "width": width if isinstance(width, int) else None,
        "height": height if isinstance(height, int) else None,
        "focal_length_35mm": f35 if isinstance(f35, int) and 5 <= f35 <= 2000 else None,
        "position": None if lat is None else {
            "latitude": lat, "longitude": lon,
            "relative_altitude_m": _num(d("RelativeAltitude"), -1000, 10000),
            "absolute_altitude_m": _num(d("AbsoluteAltitude"), -1000, 10000),
            "gps_status": _text(d("GpsStatus"), 16)},
        "gimbal": {"pitch_deg": _num(d("GimbalPitchDegree"), -180, 180),
                   "yaw_deg": _num(d("GimbalYawDegree"), -360, 360)},
    }


def field_of_view(meta: dict) -> tuple[float, float] | None:
    f35, w, h = meta.get("focal_length_35mm"), meta.get("width"), meta.get("height")
    if not f35 or not w or not h:
        return None
    t = (FULL_FRAME_DIAGONAL_MM / (2 * f35)) / math.hypot(w, h)
    return math.degrees(2 * math.atan(t * w)), math.degrees(2 * math.atan(t * h))


def photo_geometry(meta: dict) -> dict:
    view = field_of_view(meta)
    foot = ground_footprint(meta.get("position"), meta.get("gimbal"), *view,
                            account_for_pitch=True) if view else None
    gsd = None
    if foot and view and meta.get("width"):
        height = meta["position"]["relative_altitude_m"]
        tilt = math.radians((meta["gimbal"].get("pitch_deg") or -90) + 90)
        gsd = 2 * height / math.cos(tilt) * math.tan(math.radians(view[0]) / 2) / meta["width"] * 100
    return {"hfov_deg": round(view[0], 2) if view else None,
            "vfov_deg": round(view[1], 2) if view else None,
            "footprint": foot, "ground_sample_cm": round(gsd, 2) if gsd else None}


def _distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    (la1, lo1), (la2, lo2) = (map(math.radians, a)), (map(math.radians, b))
    h = (math.sin((la2 - la1) / 2) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2)
    return 2 * 6371.0 * math.asin(min(1.0, math.sqrt(h)))


def mark_position_outliers(items: list[dict]) -> int:
    """Flag positions far from their flight's median position.

    DJI sometimes writes a stale or uninitialised fix (even with status RTK)
    into the first images after power-on. Such points are kept but flagged,
    so maps do not zoom out to a continent. Flights with fewer than three
    positioned images are not judged."""
    by_flight: dict = {}
    for item in items:
        by_flight.setdefault(item.get("flight"), []).append(item)
    flagged = 0
    for group in by_flight.values():
        if len(group) < 3:
            for item in group:
                item["position_outlier"] = False
            continue
        lats = sorted(i["latitude"] for i in group)
        lons = sorted(i["longitude"] for i in group)
        centre = (lats[len(lats) // 2], lons[len(lons) // 2])
        for item in group:
            item["position_outlier"] = (
                _distance_km(centre, (item["latitude"], item["longitude"])) > OUTLIER_KM)
            flagged += item["position_outlier"]
    return flagged


class PhotoCatalog:
    def __init__(self, media_index: DjiMediaIndex):
        self.media = media_index
        self.path = media_index.root / DB_NAME

    def _connect(self, *, write: bool):
        if self.path.is_symlink():
            raise DjiMediaError("Refusing symlinked photo catalogue")
        if not self.path.exists():
            if not write:
                return None
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                         | getattr(os, "O_NOFOLLOW", 0), 0o600)
            os.close(fd)
        if not self.path.is_file() or self.path.stat().st_mode & 0o077:
            raise DjiMediaError("Photo catalogue must be a private 0600 file")
        conn = (sqlite3.connect(self.path, timeout=30) if write else
                sqlite3.connect("file:" + str(self.path) + "?mode=ro", uri=True, timeout=5))
        conn.row_factory = sqlite3.Row
        if write:
            conn.execute("""CREATE TABLE IF NOT EXISTS photos (
                id TEXT PRIMARY KEY, version_key TEXT NOT NULL, filename TEXT NOT NULL,
                model TEXT, camera TEXT, kind TEXT, captured_at TEXT, meta TEXT)""")
            conn.execute("CREATE INDEX IF NOT EXISTS photos_model ON photos(model, camera)")
            conn.execute("""CREATE TABLE IF NOT EXISTS photo_scan (id INTEGER PRIMARY KEY CHECK (id = 1),
                completed_at TEXT NOT NULL, read INTEGER NOT NULL, failed INTEGER NOT NULL)""")
        return conn

    def scan(self, client, bucket: str) -> dict:
        db = self._connect(write=True)
        read = failed = 0
        try:
            known = {r["id"]: r["version_key"] for r in db.execute("SELECT id, version_key FROM photos")}
            records = [r for r in self.media.jpeg_records() if r["bucket"] == bucket]
            with db:
                for stale in set(known) - {r["id"] for r in records}:
                    db.execute("DELETE FROM photos WHERE id=?", (stale,))
            for record in records:
                version_key = f'{record["etag"]}#v{META_VERSION}'
                if known.get(record["id"]) == version_key:
                    continue
                try:
                    stream = client.get_object(bucket, record["object_key"], offset=0,
                                               length=min(HEADER_BYTES, record["size_bytes"]))
                    try:
                        head = stream.read(HEADER_BYTES)
                    finally:
                        stream.close()
                        stream.release_conn()
                except Exception:  # MinIO errors may echo object keys: count only
                    failed += 1
                    continue
                meta = photo_metadata(head)
                with db:
                    db.execute("""INSERT INTO photos (id, version_key, filename, model, camera, kind,
                        captured_at, meta) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                        version_key=excluded.version_key, filename=excluded.filename,
                        model=excluded.model, camera=excluded.camera, kind=excluded.kind,
                        captured_at=excluded.captured_at, meta=excluded.meta""",
                               (record["id"], version_key, record["filename"],
                                meta and meta["model"], meta and meta["camera"], meta and meta["kind"],
                                meta and meta["captured_at"], json.dumps(meta) if meta else None))
                read += 1
            stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
            with db:
                db.execute("""INSERT INTO photo_scan (id, completed_at, read, failed) VALUES (1,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET completed_at=excluded.completed_at,
                    read=excluded.read, failed=excluded.failed""", (stamp, read, failed))
            total = db.execute("SELECT COUNT(*) FROM photos WHERE model IS NOT NULL").fetchone()[0]
            return {"indexed": total, "read": read, "failed": failed, "scanned_at": stamp}
        finally:
            db.close()

    # ------------------------------------------------------------ queries --
    def _rows(self, where: str = "", args: tuple = ()) -> list[sqlite3.Row]:
        db = self._connect(write=False)
        if db is None:
            return []
        try:
            return db.execute("SELECT id, filename, model, camera, kind, captured_at, meta FROM photos "
                              "WHERE model IS NOT NULL" + where, args).fetchall()
        finally:
            db.close()

    def thermal_ids(self) -> set[str]:
        """Infrared images regardless of their file name (e.g. FlightHub org_*.jpg)."""
        return {r["id"] for r in self._rows(" AND camera='InfraredCamera'")}

    def summary(self) -> dict:
        rows = self._rows()
        models: dict = {}
        for (model, camera), count in Counter((r["model"], r["camera"]) for r in rows).items():
            entry = models.setdefault(model, {"model": model, "name": MODEL_NAMES.get(model, model),
                                              "total": 0, "cameras": {}})
            entry["total"] += count
            entry["cameras"][camera or "?"] = count
        db = self._connect(write=False)
        stamp = None
        if db is not None:
            try:
                row = db.execute("SELECT completed_at FROM photo_scan WHERE id=1").fetchone()
                stamp = row[0] if row else None
            finally:
                db.close()
        return {"models": sorted(models.values(), key=lambda m: -m["total"]),
                "total": len(rows), "scanned_at": stamp, "camera_names": CAMERA_NAMES}

    def _filtered(self, model: str | None, camera: str | None) -> list[sqlite3.Row]:
        where, args = "", []
        if model:
            where += " AND model=?"
            args.append(model)
        if camera:
            where += " AND camera=?"
            args.append(camera)
        return self._rows(where, tuple(args))

    def _flight_rows(self, model, camera, flight) -> list[dict]:
        rows = [dict(r) for r in self._filtered(model, camera)]
        if flight:
            from .thermal_flights import group_flights
            match = next((f for f in group_flights(rows) if f["id"] == flight), None)
            rows = match["images"] if match else []
        return rows

    def flights(self, *, model: str | None = None, camera: str | None = None) -> list[dict]:
        from .thermal_flights import group_flights
        rows = [dict(r) for r in self._filtered(model, camera)]
        out = []
        for f in group_flights(rows):
            metas = [json.loads(r["meta"]) for r in f["images"]]
            heights = [m["position"]["relative_altitude_m"] for m in metas
                       if m.get("position") and m["position"].get("relative_altitude_m") is not None]
            out.append({"id": f["id"], "start": f["start"], "end": f["end"], "images": len(f["images"]),
                        "with_position": sum(1 for m in metas if m.get("position")),
                        "models": sorted({r["model"] for r in f["images"]}),
                        "cameras": sorted({r["camera"] or "?" for r in f["images"]}),
                        "median_altitude_m": sorted(heights)[len(heights) // 2] if heights else None})
        return out

    def list(self, *, model=None, camera=None, flight=None, limit=50, offset=0) -> dict:
        if not 1 <= limit <= 200 or not 0 <= offset <= 1_000_000:
            raise DjiMediaError("Invalid photo catalogue pagination")
        rows = self._flight_rows(model, camera, flight)
        rows.sort(key=lambda r: (r["captured_at"] or "", r["filename"]), reverse=True)
        records = self.media.get_many([r["id"] for r in rows[offset:offset + limit]])
        items = []
        for r in rows[offset:offset + limit]:
            meta, rec = json.loads(r["meta"]), records.get(r["id"]) or {}
            pos = meta.get("position") or {}
            items.append({"id": r["id"], "name": r["filename"], "model": r["model"], "camera": r["camera"],
                          "kind": r["kind"], "captured_at": r["captured_at"],
                          "size_bytes": rec.get("size_bytes"), "width": meta.get("width"),
                          "height": meta.get("height"), "focal_length_35mm": meta.get("focal_length_35mm"),
                          "relative_altitude_m": pos.get("relative_altitude_m"),
                          "gimbal_pitch_deg": (meta.get("gimbal") or {}).get("pitch_deg"),
                          "has_position": bool(pos)})
        return {"items": items, "total": len(rows), "limit": limit, "offset": offset}

    def map_items(self, *, model=None, camera=None, flight=None, limit: int = 10000) -> dict:
        from .thermal_flights import group_flights
        rows = self._flight_rows(model, camera, flight)
        flight_of = {image["id"]: f["id"] for f in group_flights(rows) for image in f["images"]}
        items, missing = [], 0
        for r in rows[:limit]:
            meta = json.loads(r["meta"])
            pos = meta.get("position")
            if not pos:
                missing += 1
                continue
            geo = photo_geometry(meta)
            items.append({"id": r["id"], "name": r["filename"], "model": r["model"], "camera": r["camera"],
                          "captured_at": r["captured_at"], "latitude": pos["latitude"],
                          "longitude": pos["longitude"], "relative_altitude_m": pos.get("relative_altitude_m"),
                          "gimbal_pitch_deg": (meta.get("gimbal") or {}).get("pitch_deg"),
                          "flight": flight_of.get(r["id"]), **geo})
        outliers = mark_position_outliers(items)
        return {"items": items, "without_position": missing, "position_outliers": outliers,
                "total": len(rows),
                "assumption": "Footprint nur bei Nadir-Aufnahmen (±15°), ebenes Gelände auf Startpunkthöhe"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only DJI photo catalogue (header range reads)")
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args(argv)
    try:
        from dotenv import load_dotenv
        from .minio_media_index import MinioMediaSettings, minio_client
        if args.env_file:
            load_dotenv(args.env_file, override=False)
        settings = MinioMediaSettings.from_env()
        catalog = PhotoCatalog(DjiMediaIndex())
        report = catalog.scan(minio_client(settings), settings.bucket)
        report["models"] = {m["model"]: m["cameras"] for m in catalog.summary()["models"]}
        print(json.dumps(report, ensure_ascii=False))
        return 1 if report["failed"] else 0
    except (DjiMediaError, OSError, sqlite3.Error) as exc:
        print("Photo catalogue error: " + str(exc).split("\n", 1)[0], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
