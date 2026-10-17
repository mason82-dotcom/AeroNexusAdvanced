"""Thermal image geometry and the private geo index for the thermal map.

Optics are the diagonal fields of view from DJI's published specifications.
Footprints assume flat terrain at the take-off elevation (``RelativeAltitude``)
and are only computed for near-nadir images; they are a planning aid, not a
survey-grade orthorectification.

The geo index (``thermal_geo.sqlite3``, 0600, in the private workspace) holds
whitelisted XMP fields of indexed thermal images. A scan reads only the first
256 KiB of each object (HTTP range request), never writes to MinIO and skips
objects whose ETag is unchanged.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
import sqlite3
import sys

from .minio_media_index import DjiMediaError, DjiMediaIndex
from .thermal import ThermalError, thermal_metadata


# Diagonal FOV in degrees (DJI spec sheets). Wide camera = the "_V"/"_W" image.
CAMERA_OPTICS = {
    "M3T": {"thermal_dfov_deg": 61.0, "visual_dfov_deg": 84.0},
    "M30T": {"thermal_dfov_deg": 61.0, "visual_dfov_deg": 84.0},
    "M4T": {"thermal_dfov_deg": 45.0, "visual_dfov_deg": 82.0},
}
NADIR_TOLERANCE_DEG = 15.0
HEADER_BYTES = 256 * 1024
DB_NAME = "thermal_geo.sqlite3"
EARTH_M_PER_DEG = 111_320.0


def optics_for(model: str | None) -> dict | None:
    if not isinstance(model, str):
        return None
    key = model.strip().upper()
    for name, optics in CAMERA_OPTICS.items():
        if key == name or key.startswith(name):
            return {"camera": name, **optics, "source": "DJI-Datenblatt (diagonales Sichtfeld)"}
    return None


def fov(dfov_deg: float, width: int, height: int) -> tuple[float, float]:
    """Horizontal and vertical FOV (deg) of a rectilinear image from its diagonal FOV."""
    t = math.tan(math.radians(dfov_deg) / 2) / math.hypot(width, height)
    return (math.degrees(2 * math.atan(t * width)), math.degrees(2 * math.atan(t * height)))


def _raster(meta: dict) -> tuple[int, int]:
    # Radiometric raster of all supported cameras is 640x512; the JPEG size can
    # be 2x (M4T super resolution) and is unknown after a header-only read.
    return meta.get("raw_width") or 640, meta.get("raw_height") or 512


def _thermal_fov(meta: dict) -> tuple[float, float] | None:
    optics = optics_for(meta.get("model"))
    return fov(optics["thermal_dfov_deg"], *_raster(meta)) if optics else None


def slant_distance_m(meta: dict) -> float | None:
    """Camera-to-ground distance along the optical axis over flat terrain."""
    pos, gimbal = meta.get("position") or {}, meta.get("gimbal") or {}
    height, pitch = pos.get("relative_altitude_m"), gimbal.get("pitch_deg")
    if not isinstance(height, (int, float)) or height <= 1 or not isinstance(pitch, (int, float)):
        return None
    if pitch > -20:  # near-horizontal view: no ground intersection worth reporting
        return None
    return height / math.sin(math.radians(-pitch))


def ground_sample_m(meta: dict) -> float | None:
    """Thermal pixel size on the ground at the image centre (m/px)."""
    view, dist = _thermal_fov(meta), slant_distance_m(meta)
    if view is None or dist is None:
        return None
    return 2 * dist * math.tan(math.radians(view[0]) / 2) / _raster(meta)[0]


def _offset(lat0: float, lon0: float, north: float, east: float) -> list[float]:
    return [round(lat0 + north / EARTH_M_PER_DEG, 8),
            round(lon0 + east / (EARTH_M_PER_DEG * math.cos(math.radians(lat0))), 8)]


def ground_footprint(position: dict | None, gimbal: dict | None, hfov_deg: float,
                     vfov_deg: float, *, account_for_pitch: bool = False) -> list[list[float]] | None:
    """Ground corners [[lat, lon] x4] (image top-left, top-right, bottom-right,
    bottom-left) of a near-nadir image over flat terrain, else None.

    ``account_for_pitch`` intersects tilted camera rays with the ground plane.
    The default preserves the legacy rectangle used by the thermal viewer.
    """
    gimbal = gimbal or {}
    if not position:
        return None
    height, pitch, yaw = (position.get("relative_altitude_m"), gimbal.get("pitch_deg"),
                          gimbal.get("yaw_deg"))
    if (not isinstance(height, (int, float)) or height <= 1 or not isinstance(pitch, (int, float))
            or abs(pitch + 90) > NADIR_TOLERANCE_DEG or not isinstance(yaw, (int, float))):
        return None
    half_r = math.tan(math.radians(hfov_deg) / 2)  # image x (right)
    half_f = math.tan(math.radians(vfov_deg) / 2)  # image up
    tilt = math.radians(pitch + 90) if account_for_pitch else 0.0
    st, ct = math.sin(tilt), math.cos(tilt)
    y = math.radians(yaw)
    fwd, right = (math.cos(y), math.sin(y)), (-math.sin(y), math.cos(y))  # (north, east)
    corners = []
    for f, r in ((half_f, -half_r), (half_f, half_r), (-half_f, half_r), (-half_f, -half_r)):
        down = ct - f * st
        if down <= 0:
            return None  # a ray reaches the horizon, not the ground plane
        distance = height / down
        forward = st + f * ct
        corners.append(_offset(position["latitude"], position["longitude"],
                               distance * (forward * fwd[0] + r * right[0]),
                               distance * (forward * fwd[1] + r * right[1])))
    return corners


def view_cone(position: dict | None, gimbal: dict | None, hfov_deg: float, *,
              length_m: float = 15.0) -> list[list[float]] | None:
    """Triangle [[lat, lon] x3] showing the horizontal viewing direction of an
    oblique image (camera position and the two edges of the field of view)."""
    yaw = (gimbal or {}).get("yaw_deg")
    if not position or not isinstance(yaw, (int, float)):
        return None
    lat0, lon0 = position["latitude"], position["longitude"]
    points = [[round(lat0, 8), round(lon0, 8)]]
    for edge in (-hfov_deg / 2, hfov_deg / 2):
        a = math.radians(yaw + edge)
        points.append(_offset(lat0, lon0, length_m * math.cos(a), length_m * math.sin(a)))
    return points


def footprint(meta: dict) -> list[list[float]] | None:
    """Thermal image footprint (see ground_footprint), with the same tilted-ray
    projection as the multispectral map so both maps agree for −75…−105°."""
    view = _thermal_fov(meta)
    return None if view is None else ground_footprint(meta.get("position"), meta.get("gimbal"),
                                                      *view, account_for_pitch=True)


def geometry(meta: dict) -> dict:
    view = _thermal_fov(meta)
    gsd = ground_sample_m(meta)
    return {"optics": optics_for(meta.get("model")),
            "thermal_hfov_deg": round(view[0], 2) if view else None,
            "thermal_vfov_deg": round(view[1], 2) if view else None,
            "slant_distance_m": round(slant_distance_m(meta), 2) if slant_distance_m(meta) else None,
            "ground_sample_cm": round(gsd * 100, 2) if gsd else None,
            "footprint": footprint(meta),
            "assumption": "ebenes Gelände auf Startpunkthöhe (RelativeAltitude)"}


# ------------------------------------------------------------ geo index ----

class ThermalGeoIndex:
    def __init__(self, media_index: DjiMediaIndex):
        self.media = media_index
        self.path = media_index.root / DB_NAME

    def _connect(self, *, write: bool) -> sqlite3.Connection | None:
        if self.path.is_symlink():
            raise DjiMediaError("Refusing symlinked thermal geo index")
        if not self.path.exists():
            if not write:
                return None
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                         | getattr(os, "O_NOFOLLOW", 0), 0o600)
            os.close(fd)
        if not self.path.is_file() or self.path.stat().st_mode & 0o077:
            raise DjiMediaError("Thermal geo index must be a private 0600 file")
        conn = (sqlite3.connect(self.path, timeout=30) if write else
                sqlite3.connect("file:" + str(self.path) + "?mode=ro", uri=True, timeout=5))
        conn.row_factory = sqlite3.Row
        if write:
            conn.execute("""CREATE TABLE IF NOT EXISTS thermal_geo (
                id TEXT PRIMARY KEY, etag TEXT, filename TEXT NOT NULL,
                captured_at TEXT, model TEXT, meta TEXT NOT NULL)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS thermal_stats (
                id TEXT PRIMARY KEY, etag TEXT, stats TEXT NOT NULL, computed_at TEXT NOT NULL)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS thermal_geo_scan (
                id INTEGER PRIMARY KEY CHECK (id = 1), completed_at TEXT NOT NULL,
                indexed INTEGER NOT NULL, read INTEGER NOT NULL, failed INTEGER NOT NULL)""")
        return conn

    def scan(self, client, bucket: str, *, limit: int | None = None) -> dict:
        """Index new/changed thermal images; prune entries gone from the media index."""
        db = self._connect(write=True)
        read = failed = 0
        try:
            known = {row["id"]: row["etag"] for row in db.execute("SELECT id, etag FROM thermal_geo")}
            records = [r for r in self.media.thermal_records() if r["bucket"] == bucket]
            with db:
                current = {r["id"] for r in records}
                for stale in set(known) - current:
                    db.execute("DELETE FROM thermal_geo WHERE id=?", (stale,))
            for record in records:
                if known.get(record["id"]) == record["etag"] and record["id"] in known:
                    continue
                if limit is not None and read + failed >= limit:
                    break
                try:
                    stream = client.get_object(bucket, record["object_key"], offset=0,
                                               length=min(HEADER_BYTES, record["size_bytes"]))
                    try:
                        head = stream.read(HEADER_BYTES)
                    finally:
                        stream.close()
                        stream.release_conn()
                    meta = thermal_metadata(head, partial=True)
                except ThermalError:
                    failed += 1
                    continue
                except Exception:  # MinIO errors may echo object keys: count only
                    failed += 1
                    continue
                with db:
                    db.execute("""INSERT INTO thermal_geo (id, etag, filename, captured_at, model, meta)
                        VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET etag=excluded.etag,
                        filename=excluded.filename, captured_at=excluded.captured_at,
                        model=excluded.model, meta=excluded.meta""",
                               (record["id"], record["etag"], record["filename"],
                                meta["captured_at"], meta["model"], json.dumps(meta)))
                read += 1
            total = db.execute("SELECT COUNT(*) FROM thermal_geo").fetchone()[0]
            stamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            with db:
                db.execute("""INSERT INTO thermal_geo_scan (id, completed_at, indexed, read, failed)
                    VALUES (1,?,?,?,?) ON CONFLICT(id) DO UPDATE SET completed_at=excluded.completed_at,
                    indexed=excluded.indexed, read=excluded.read, failed=excluded.failed""",
                           (stamp, total, read, failed))
            return {"indexed": total, "read": read, "failed": failed, "scanned_at": stamp}
        finally:
            db.close()

    def map_items(self, *, limit: int = 5000) -> dict:
        db = self._connect(write=False)
        if db is None:
            return {"items": [], "indexed": 0, "scanned_at": None, "without_position": 0}
        try:
            items, missing = [], 0
            for row in db.execute("SELECT * FROM thermal_geo ORDER BY filename DESC LIMIT ?", (limit,)):
                meta = json.loads(row["meta"])
                pos = meta.get("position")
                if not pos:
                    missing += 1
                    continue
                geo = geometry(meta)
                gimbal = meta.get("gimbal") or {}
                items.append({
                    "id": row["id"], "name": row["filename"], "captured_at": row["captured_at"],
                    "model": row["model"], "latitude": pos["latitude"], "longitude": pos["longitude"],
                    "relative_altitude_m": pos.get("relative_altitude_m"),
                    "gimbal_yaw_deg": gimbal.get("yaw_deg"), "gimbal_pitch_deg": gimbal.get("pitch_deg"),
                    "ground_sample_cm": geo["ground_sample_cm"], "footprint": geo["footprint"],
                })
            scan = db.execute("SELECT * FROM thermal_geo_scan WHERE id=1").fetchone()
            return {"items": items, "indexed": scan["indexed"] if scan else len(items) + missing,
                    "scanned_at": scan["completed_at"] if scan else None,
                    "without_position": missing}
        finally:
            db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only thermal geo index (range-reads image headers, no MinIO writes)")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--limit", type=int, default=None, help="max. images to read in this run")
    args = parser.parse_args(argv)
    try:
        from dotenv import load_dotenv
        from .minio_media_index import MinioMediaSettings, minio_client
        if args.env_file:
            load_dotenv(args.env_file, override=False)
        settings = MinioMediaSettings.from_env()
        report = ThermalGeoIndex(DjiMediaIndex()).scan(minio_client(settings), settings.bucket,
                                                       limit=args.limit)
        print(json.dumps(report))
        return 0
    except (DjiMediaError, OSError, sqlite3.Error) as exc:
        print("Thermal geo index error: " + str(exc).split("\n", 1)[0], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


