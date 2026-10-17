"""DJI Mavic 3 Multispectral (M3M): band catalogue, radiometry and indices.

Processing follows DJI's *Mavic 3M Image Processing Guide* v1.0 (2023-08):

1. camera signal  X_cam = (I/2^bits - Black/2^bits) / (gain * t_exp/1e6)   (Eq. 9)
2. vignetting     X_cam * (k5 r^6 + ... + k0 r + 1), r from the calibrated
                  optical centre                                            (Eq. 7/8)
3. lens distortion (Dewarp Data: fx, fy, cx, cy, k1, k2, p1, p2, k3)
4. band alignment with the Calibrated HMatrix (real -> designed plane)
5. relative reflectance  X_cam * SensorGainAdjustment / Irradiance           (Eq. 4-6)

The common factor rho_NIR of Eq. 4/5 is unknown without a reflectance
panel, so values are *relative* reflectance. Normalised-difference indices
(NDVI, GNDVI, NDRE, LCI) are exact per Eq. 6 because rho_NIR cancels. The
guide's optional step 4 (ECC/feature alignment for exposure-time offsets
during fast flight) is not implemented.

Read-only: band files are read from the MinIO index by opaque id with an
ETag check; a catalogue scan range-reads only the first 256 KiB per file.
Serial numbers, NTRIP data and unknown vendor fields are never returned.
"""
from __future__ import annotations

import argparse
from collections import OrderedDict
from datetime import datetime, timezone
import json
import math
import os
from pathlib import PurePosixPath
import re
import sqlite3
import struct
import sys
import threading

from .minio_media_index import DjiMediaChanged, DjiMediaError, DjiMediaIndex
from .processing_slot import ProcessingSlot
from .thermal import ThermalError, _num, _text, _xmp_fields, jpeg_segments


class MultispectralError(ValueError):
    pass


class MultispectralNotFound(MultispectralError):
    pass


class MultispectralBusy(MultispectralError):
    """Another band is being processed; retry later (bounded RAM on the Pi)."""


BANDS = ("Green", "Red", "RedEdge", "NIR")
BAND_KEYS = {"Green": "g", "Red": "r", "RedEdge": "re", "NIR": "nir"}
INDICES = {
    "ndvi": ("NDVI", ("NIR", "Red"), "(NIR − Rot) / (NIR + Rot)"),
    "gndvi": ("GNDVI", ("NIR", "Green"), "(NIR − Grün) / (NIR + Grün)"),
    "ndre": ("NDRE", ("NIR", "RedEdge"), "(NIR − RedEdge) / (NIR + RedEdge)"),
    "lci": ("LCI", ("NIR", "RedEdge", "Red"), "(NIR − RedEdge) / (NIR + Rot)"),
}
LAYERS = (*INDICES, *(f"band_{v}" for v in BAND_KEYS.values()))
NDVI_CLASSES = ((-1.0, 0.0, "kein Bewuchs / Wasser"), (0.0, 0.2, "offener Boden / kaum Bewuchs"),
                (0.2, 0.4, "schwacher Bewuchs"), (0.4, 0.6, "mäßiger Bewuchs"),
                (0.6, 1.0001, "dichter, vitaler Bewuchs"))
HEADER_BYTES = 256 * 1024
MAX_BAND_BYTES = 64 * 1024 * 1024
MAX_SIDE = 8192
DB_NAME = "multispectral.sqlite3"
META_VERSION = "2"  # bump when band_metadata gains fields: forces a header re-read
PROCESSING_VERSION = "2"  # invalidates persisted summaries after quality/geometry fixes
_UUID_RE = re.compile(r"[0-9a-f]{32}\Z")


def _np():
    try:
        import numpy
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise MultispectralError("Install optional dependency: pip install -e '.[multispectral]'") from exc
    return numpy


# ---------------------------------------------------------------- TIFF ----

_TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 11: 4, 12: 8, 16: 8}


def tiff_structure(data: bytes, *, partial: bool = False) -> dict:
    """First IFD of a baseline TIFF: size, layout and XMP, without decoding."""
    if not isinstance(data, (bytes, bytearray)) or len(data) < 8 or data[:4] not in (b"II*\x00", b"MM\x00*"):
        raise MultispectralError("Not a TIFF image")
    bo = "<" if data[:2] == b"II" else ">"
    offset = struct.unpack(bo + "I", data[4:8])[0]
    if offset + 2 > len(data):
        raise MultispectralError("TIFF directory outside the read data")
    count = struct.unpack(bo + "H", data[offset:offset + 2])[0]
    if count > 512 or offset + 2 + count * 12 > len(data):
        raise MultispectralError("Malformed TIFF directory")
    tags = {}
    for i in range(count):
        tag, typ, n, raw = struct.unpack(bo + "HHI4s", data[offset + 2 + i * 12:offset + 14 + i * 12])
        size = _TYPE_SIZE.get(typ, 1) * n
        if size <= 4:
            blob = raw[:size]
        else:
            start = struct.unpack(bo + "I", raw)[0]
            if start + size > len(data):
                if partial:
                    continue
                raise MultispectralError("TIFF tag outside the file")
            blob = data[start:start + size]
        if typ in (3, 4):
            fmt = "H" if typ == 3 else "I"
            tags[tag] = list(struct.unpack(bo + fmt * n, blob[:size]))
        elif typ in (1, 2, 7):
            tags[tag] = bytes(blob)
    first = lambda t, default=None: (tags.get(t) or [default])[0]  # noqa: E731
    info = {
        "byteorder": bo, "width": first(256), "height": first(257), "bits": first(258),
        "compression": first(259, 1), "samples": first(277, 1),
        "strip_offsets": tags.get(273, []), "strip_counts": tags.get(279, []),
        "xmp": tags[700].decode("utf-8", "replace") if 700 in tags else None,
    }
    if not (isinstance(info["width"], int) and isinstance(info["height"], int)
            and 0 < info["width"] <= MAX_SIDE and 0 < info["height"] <= MAX_SIDE):
        raise MultispectralError("Unsupported TIFF size")
    return info


def read_band(data: bytes):
    """Decode an uncompressed single-channel 16-bit (or 8-bit) TIFF band."""
    np = _np()
    info = tiff_structure(data)
    if info["compression"] != 1 or info["samples"] != 1 or info["bits"] not in (8, 16):
        raise MultispectralError("Only uncompressed single-band 8/16-bit TIFF is supported")
    if not info["strip_offsets"] or len(info["strip_offsets"]) != len(info["strip_counts"]):
        raise MultispectralError("TIFF strips missing")
    expected = info["width"] * info["height"] * info["bits"] // 8
    chunks = []
    for start, size in zip(info["strip_offsets"], info["strip_counts"]):
        if start + size > len(data):
            raise MultispectralError("TIFF strip outside the file")
        chunks.append(data[start:start + size])
    raw = b"".join(chunks)
    if len(raw) < expected:
        raise MultispectralError("TIFF pixel data incomplete")
    dtype = np.dtype(info["byteorder"] + ("u2" if info["bits"] == 16 else "u1"))
    return np.frombuffer(raw[:expected], dtype=dtype).reshape(info["height"], info["width"]), info


# ------------------------------------------------------------ metadata ----

def _floats(value, count: int) -> list[float] | None:
    if not isinstance(value, str):
        return None
    parts = [p for p in re.split(r"[,\s]+", value.split(";")[-1].strip()) if p]
    if len(parts) != count:
        return None
    out = [_num(p, -1e12, 1e12) for p in parts]
    return None if any(v is None for v in out) else out


def band_metadata(xmp: str | None) -> dict:
    """Whitelisted M3M XMP: geometry, calibration and sunlight-sensor values."""
    x = _xmp_fields(xmp)
    d = lambda name: x.get("drone-dji:" + name)  # noqa: E731
    lat = _num(d("GpsLatitude"), -90, 90)
    lon = _num(d("GpsLongitude") or d("GpsLongtitude"), -180, 180)
    if lat is None or lon is None or (abs(lat) < 1e-4 and abs(lon) < 1e-4):
        lat = lon = None
    band = d("BandName") if d("BandName") in BANDS else None
    uuid = (d("CaptureUUID") or "").lower()
    dewarp = _floats(d("DewarpData"), 9)
    return {
        "model": _text(x.get("tiff:Model") or d("DroneModel")),
        "image_source": _text(d("ImageSource")),
        "band": band, "band_freq": _text(d("BandFreq")),
        "capture_uuid": uuid if _UUID_RE.fullmatch(uuid) else None,
        "captured_at": _text(x.get("xmp:CreateDate")),
        "position": None if lat is None else {
            "latitude": lat, "longitude": lon,
            "relative_altitude_m": _num(d("RelativeAltitude"), -1000, 10000),
            "absolute_altitude_m": _num(d("AbsoluteAltitude"), -1000, 10000),
            "gps_status": _text(d("GpsStatus"), 16)},
        "gimbal": {"pitch_deg": _num(d("GimbalPitchDegree"), -180, 180),
                   "yaw_deg": _num(d("GimbalYawDegree"), -360, 360)},
        "calibration": None if band is None else {
            "black_level": _num(d("BlackLevel"), 0, 65535),
            "sensor_gain": _num(d("SensorGain"), 1e-6, 1e6),
            "exposure_time_us": _num(d("ExposureTime"), 1, 1e8),
            "sensor_gain_adjustment": _num(d("SensorGainAdjustment"), 1e-6, 1e6),
            "irradiance": _num(d("Irradiance"), 0, 1e7),
            "sunlight_sensor_status": _num(d("LS_status"), 0, 10),
            "vignetting": _floats(d("VignettingData"), 6),
            "focal_length_px": _num(d("CalibratedFocalLength"), 1, 1e6),
            "center_x": _num(d("CalibratedOpticalCenterX"), 0, MAX_SIDE),
            "center_y": _num(d("CalibratedOpticalCenterY"), 0, MAX_SIDE),
            "dewarp": dewarp,
            "h_matrix": _floats(d("CalibratedHMatrix"), 9),
        },
    }


def item_metadata(name: str, head: bytes) -> dict | None:
    """Catalogue entry from the first bytes of a TIFF band or M3M JPEG."""
    if head[:4] in (b"II*\x00", b"MM\x00*"):
        meta = band_metadata(tiff_structure(head, partial=True)["xmp"])
        kind = "band"
    elif head[:2] == b"\xff\xd8":
        try:
            xmp = jpeg_segments(head, partial=True)["xmp"]
        except ThermalError:
            return None
        meta = band_metadata(xmp)
        kind = "rgb" if (meta["image_source"] or "").lower() in ("", "rgb", "visible_camera") \
            or PurePosixPath(name).stem.upper().endswith("_D") else "preview"
    else:
        return None
    if meta["capture_uuid"] is None or (kind == "band" and meta["band"] is None):
        return None
    if not (meta["model"] or "").upper().startswith("M3M"):
        return None
    meta["kind"] = kind
    return meta


# ---------------------------------------------------------- processing ----

def relative_reflectance(dn, info: dict, cal: dict):
    """Steps 1, 2 and 5 on the raw sensor grid (float32)."""
    np = _np()
    needed = ("black_level", "sensor_gain", "exposure_time_us", "sensor_gain_adjustment", "irradiance")
    if any(cal.get(k) is None for k in needed):
        raise MultispectralError("Band calibration metadata incomplete")
    if cal.get("sunlight_sensor_status") not in (1, 2):
        raise MultispectralError("Sonnenlichtsensor ungültig oder Status fehlt; keine Reflexionsberechnung")
    if not math.isfinite(cal["irradiance"]) or cal["irradiance"] <= 1:
        raise MultispectralError("Sonnenlichtsensor ohne verwertbaren Einstrahlungswert (Irradiance ≤ 1)")
    if any(not math.isfinite(cal[k]) or cal[k] <= 0 for k in
           ("sensor_gain", "exposure_time_us", "sensor_gain_adjustment")):
        raise MultispectralError("Band calibration gain/exposure invalid")
    scale = float(2 ** info["bits"])
    signal = (dn.astype(np.float32) - np.float32(cal["black_level"])) / np.float32(scale)
    # Below-black and saturated pixels cannot provide quantitative reflectance.
    signal[(dn <= cal["black_level"]) | (dn >= scale - 1)] = np.nan
    signal /= np.float32(cal["sensor_gain"] * cal["exposure_time_us"] / 1e6)
    k = cal.get("vignetting")
    if k:
        h, w = dn.shape
        cx = cal.get("center_x") if cal.get("center_x") is not None else w / 2
        cy = cal.get("center_y") if cal.get("center_y") is not None else h / 2
        yy, xx = np.ogrid[0:h, 0:w]
        r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2, dtype=np.float32)
        poly = np.ones_like(r)
        power = np.ones_like(r)
        for coefficient in k:
            power *= r
            poly += np.float32(coefficient) * power
        signal *= poly
    signal *= np.float32(cal["sensor_gain_adjustment"] / cal["irradiance"])
    signal[~np.isfinite(signal) | (signal <= 0)] = np.nan
    return signal


RECTIFY_BLOCK_ROWS = 128  # output rows per block: bounds temporary memory on the Pi


def rectify(image, cal: dict, *, scale: int = 2):
    """Steps 3 and 4: undistort and warp into the designed image plane,
    sampled bilinearly every ``scale`` pixels (NaN outside the sensor).

    Processed in blocks of output rows so the float64 coordinate grids stay
    small (full resolution in one pass needed > 1 GB of temporaries)."""
    np = _np()
    h, w = image.shape
    oh, ow = h // scale, w // scale
    cx0 = cal.get("center_x") if cal.get("center_x") is not None else w / 2
    cy0 = cal.get("center_y") if cal.get("center_y") is not None else h / 2
    inv = None
    H = cal.get("h_matrix")
    if H:
        try:
            matrix = np.array(H, dtype=np.float64).reshape(3, 3)
            if not np.isfinite(matrix).all() or np.linalg.cond(matrix) > 1e12:
                raise ValueError("Invalid homography")
            inv = np.linalg.inv(matrix)
        except (ValueError, np.linalg.LinAlgError) as exc:
            raise MultispectralError("Band calibration HMatrix invalid or singular") from exc
    dw = cal.get("dewarp")
    if dw and (len(dw) != 9 or not np.isfinite(dw).all() or dw[0] <= 0 or dw[1] <= 0):
        raise MultispectralError("Band calibration DewarpData invalid")
    out = np.empty((oh, ow), dtype=np.float32)
    cols = (np.arange(ow, dtype=np.float64) + 0.5) * scale - 0.5
    for r0 in range(0, oh, RECTIFY_BLOCK_ROWS):
        r1 = min(oh, r0 + RECTIFY_BLOCK_ROWS)
        rows = (np.arange(r0, r1, dtype=np.float64) + 0.5) * scale - 0.5
        u, v = np.meshgrid(cols, rows)
        if inv is not None:
            den = inv[2, 0] * u + inv[2, 1] * v + inv[2, 2]
            den = np.where(np.abs(den) > 1e-12, den, np.nan)
            with np.errstate(divide="ignore", invalid="ignore"):
                u, v = ((inv[0, 0] * u + inv[0, 1] * v + inv[0, 2]) / den,
                        (inv[1, 0] * u + inv[1, 1] * v + inv[1, 2]) / den)
        if dw:
            fx, fy, cx, cy, k1, k2, p1, p2, k3 = dw
            ccx, ccy = cx0 + cx, cy0 + cy
            x, y = (u - ccx) / fx, (v - ccy) / fy
            r2 = x * x + y * y
            radial = 1 + k1 * r2 + k2 * r2 * r2 + k3 * r2 * r2 * r2
            xd = x * radial + 2 * p1 * x * y + p2 * (r2 + 2 * x * x)
            yd = y * radial + p1 * (r2 + 2 * y * y) + 2 * p2 * x * y
            u, v = fx * xd + ccx, fy * yd + ccy
        valid = np.isfinite(u) & np.isfinite(v) & (u >= 0) & (v >= 0) & (u < w - 1) & (v < h - 1)
        u, v = np.where(valid, u, 0), np.where(valid, v, 0)
        x0c = np.clip(np.floor(u).astype(np.int64), 0, w - 2)
        y0c = np.clip(np.floor(v).astype(np.int64), 0, h - 2)
        fx_, fy_ = (u - x0c).astype(np.float32), (v - y0c).astype(np.float32)
        a, b = image[y0c, x0c], image[y0c, x0c + 1]
        c, d = image[y0c + 1, x0c], image[y0c + 1, x0c + 1]
        block = (a * (1 - fx_) + b * fx_) * (1 - fy_) + (c * (1 - fx_) + d * fx_) * fy_
        block[~valid] = np.nan
        out[r0:r1] = block
    return out


def compute_layer(layer: str, bands: dict):
    np = _np()
    if layer.startswith("band_"):
        name = {v: k for k, v in BAND_KEYS.items()}[layer[5:]]
        return bands[name]
    _, needed, _ = INDICES[layer]
    if len({bands[name].shape for name in needed}) != 1:
        raise MultispectralError("Band raster dimensions differ")
    nir = bands["NIR"]
    with np.errstate(divide="ignore", invalid="ignore"):
        if layer == "lci":
            out = (nir - bands["RedEdge"]) / (nir + bands["Red"])
        else:
            other = bands[needed[1]]
            out = (nir - other) / (nir + other)
    valid = np.isfinite(out)
    for name in needed:
        valid &= np.isfinite(bands[name]) & (bands[name] > 0)
    out[~valid] = np.nan
    return out.astype(np.float32)


def layer_stats(layer: str, grid) -> dict:
    np = _np()
    finite = grid[np.isfinite(grid)]
    if finite.size == 0:
        raise MultispectralError("No valid pixels in this layer")
    p = np.percentile(finite, [2, 5, 50, 95, 98])
    stats = {"min": float(finite.min()), "max": float(finite.max()), "mean": float(finite.mean()),
             "p02": float(p[0]), "p05": float(p[1]), "median": float(p[2]), "p95": float(p[3]),
             "p98": float(p[4]), "valid_pixels": int(finite.size), "pixels": int(grid.size)}
    stats = {k: (round(v, 5) if isinstance(v, float) else v) for k, v in stats.items()}
    if layer == "ndvi":
        stats["classes"] = [{"from": lo, "to": min(hi, 1.0), "label": label,
                             "share": round(float(((finite >= lo) & (finite < hi)).mean()), 4)}
                            for lo, hi, label in NDVI_CLASSES]
    return stats


def _ms_optics(cal: dict) -> dict | None:
    """Field of view of the multispectral camera from its calibrated focal length
    (M3M: 2170 px, 2592x1944 -> about 61.7 x 48.3 deg, 73.5 deg diagonal)."""
    f = cal.get("focal_length_px")
    cx, cy = cal.get("center_x"), cal.get("center_y")
    if not f or not cx or not cy:
        return None
    width, height = 2 * cx, 2 * cy
    return {"focal_length_px": f, "width": int(width), "height": int(height),
            "hfov_deg": round(math.degrees(2 * math.atan(width / 2 / f)), 2),
            "vfov_deg": round(math.degrees(2 * math.atan(height / 2 / f)), 2)}


# ------------------------------------------------------------ catalogue ----

class MultispectralCatalog:
    """Private SQLite catalogue of M3M bands and RGB images, grouped by capture."""

    def __init__(self, media_index: DjiMediaIndex):
        self.media = media_index
        self.path = media_index.root / DB_NAME

    def _connect(self, *, write: bool):
        if self.path.is_symlink():
            raise DjiMediaError("Refusing symlinked multispectral catalogue")
        if not self.path.exists():
            if not write:
                return None
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                         | getattr(os, "O_NOFOLLOW", 0), 0o600)
            os.close(fd)
        if not self.path.is_file() or self.path.stat().st_mode & 0o077:
            raise DjiMediaError("Multispectral catalogue must be a private 0600 file")
        conn = (sqlite3.connect(self.path, timeout=30) if write else
                sqlite3.connect("file:" + str(self.path) + "?mode=ro", uri=True, timeout=5))
        conn.row_factory = sqlite3.Row
        if write:
            conn.execute("""CREATE TABLE IF NOT EXISTS ms_items (
                id TEXT PRIMARY KEY, etag TEXT, filename TEXT NOT NULL, capture_uuid TEXT,
                kind TEXT, band TEXT, captured_at TEXT, meta TEXT)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS ms_scan (id INTEGER PRIMARY KEY CHECK (id = 1),
                completed_at TEXT NOT NULL, read INTEGER NOT NULL, failed INTEGER NOT NULL)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS ms_summary (
                capture_uuid TEXT PRIMARY KEY, source_key TEXT NOT NULL, layer TEXT NOT NULL,
                stats TEXT NOT NULL, computed_at TEXT NOT NULL)""")
        return conn

    def scan(self, client, bucket: str) -> dict:
        db = self._connect(write=True)
        read = failed = 0
        try:
            known = {r["id"]: r["etag"] for r in db.execute("SELECT id, etag FROM ms_items")}
            records = [r for r in self.media.multispectral_candidates() if r["bucket"] == bucket]
            with db:
                for stale in set(known) - {r["id"] for r in records}:
                    db.execute("DELETE FROM ms_items WHERE id=?", (stale,))
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
                    meta = item_metadata(record["filename"], head)
                except (MultispectralError, ThermalError):
                    meta = None
                except Exception:  # MinIO errors may echo object keys: count only
                    failed += 1
                    continue
                with db:
                    db.execute("""INSERT INTO ms_items (id, etag, filename, capture_uuid, kind, band,
                        captured_at, meta) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                        etag=excluded.etag, filename=excluded.filename,
                        capture_uuid=excluded.capture_uuid, kind=excluded.kind, band=excluded.band,
                        captured_at=excluded.captured_at, meta=excluded.meta""",
                               (record["id"], version_key, record["filename"],
                                meta and meta["capture_uuid"], meta and meta["kind"],
                                meta and meta["band"], meta and meta["captured_at"],
                                json.dumps(meta) if meta else None))
                read += 1
            stamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            with db:
                db.execute("""INSERT INTO ms_scan (id, completed_at, read, failed) VALUES (1,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET completed_at=excluded.completed_at,
                    read=excluded.read, failed=excluded.failed""", (stamp, read, failed))
            captures = db.execute("SELECT COUNT(DISTINCT capture_uuid) FROM ms_items "
                                  "WHERE capture_uuid IS NOT NULL").fetchone()[0]
            return {"read": read, "failed": failed, "captures": captures, "scanned_at": stamp}
        finally:
            db.close()

    def _rows(self, capture_uuid: str | None = None) -> list[sqlite3.Row]:
        db = self._connect(write=False)
        if db is None:
            return []
        try:
            sql = "SELECT * FROM ms_items WHERE capture_uuid IS NOT NULL"
            args: tuple = ()
            if capture_uuid:
                sql += " AND capture_uuid=?"
                args = (capture_uuid,)
            return db.execute(sql + " ORDER BY captured_at DESC, filename", args).fetchall()
        finally:
            db.close()

    def scanned_at(self) -> str | None:
        db = self._connect(write=False)
        if db is None:
            return None
        try:
            row = db.execute("SELECT completed_at FROM ms_scan WHERE id=1").fetchone()
            return row[0] if row else None
        finally:
            db.close()

    def captures(self) -> list[dict]:
        groups: OrderedDict = OrderedDict()
        for row in self._rows():
            groups.setdefault(row["capture_uuid"], []).append(row)
        captures = [self._capture(uuid, rows) for uuid, rows in groups.items()]
        return [c for c in captures if c["bands"]]  # RGB-only M3M shots are not multispectral

    def capture(self, capture_uuid: str) -> dict:
        if not isinstance(capture_uuid, str) or not _UUID_RE.fullmatch(capture_uuid):
            raise MultispectralNotFound("Unknown capture")
        rows = self._rows(capture_uuid)
        if not rows:
            raise MultispectralNotFound("Unknown capture")
        return self._capture(capture_uuid, rows)

    def store_summary(self, capture_uuid: str, source_key: str, layer: str, stats: dict) -> None:
        db = self._connect(write=True)
        try:
            with db:
                db.execute("""INSERT INTO ms_summary (capture_uuid, source_key, layer, stats, computed_at)
                    VALUES (?,?,?,?,?) ON CONFLICT(capture_uuid) DO UPDATE SET
                    source_key=excluded.source_key, layer=excluded.layer, stats=excluded.stats,
                    computed_at=excluded.computed_at""",
                           (capture_uuid, source_key, layer, json.dumps(stats),
                            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")))
        finally:
            db.close()

    def assert_current(self, capture: dict) -> None:
        """Reject a media index ahead of (or missing items from) this catalogue.

        A media-sync scan can complete before the following header scan. Comparing
        catalogue snapshots alone would miss that interval and allow new rasters
        to be labelled with stale capture metadata.
        """
        bands = capture["bands"]
        records = self.media.get_many([band["id"] for band in bands.values()])
        sources = []
        for name, band in bands.items():
            record = records.get(band["id"])
            if record is None:
                raise DjiMediaChanged("Band no longer indexed")
            sources.append(f'{name}:{record["id"]}:{record["etag"]}#v{META_VERSION}')
        source_key = PROCESSING_VERSION + "|" + "|".join(sorted(sources))
        if source_key != capture["source_key"]:
            raise DjiMediaChanged("Multispectral catalogue requires refresh")

    def summaries(self) -> dict[str, tuple[str, dict]]:
        db = self._connect(write=False)
        if db is None:
            return {}
        try:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='ms_summary'").fetchone():
                return {}
            return {r["capture_uuid"]: (r["source_key"], json.loads(r["stats"]))
                    for r in db.execute("SELECT * FROM ms_summary")}
        finally:
            db.close()

    @staticmethod
    def _capture(uuid: str, rows) -> dict:
        bands, rgb, preview, band_meta, other_meta, optics = {}, None, None, None, None, None
        sources = []
        for row in rows:
            meta = json.loads(row["meta"])
            if row["kind"] == "band" and row["band"] in BANDS and row["band"] not in bands:
                cal = meta.get("calibration") or {}
                sources.append(f'{row["band"]}:{row["id"]}:{row["etag"]}')
                optics = optics or _ms_optics(cal)
                bands[row["band"]] = {"id": row["id"], "name": row["filename"],
                                      "irradiance": cal.get("irradiance"),
                                      "sunlight_sensor_status": cal.get("sunlight_sensor_status"),
                                      "exposure_time_us": cal.get("exposure_time_us"),
                                      "sensor_gain": cal.get("sensor_gain"),
                                      "band_freq": meta.get("band_freq")}
                band_meta = band_meta or meta
            elif row["kind"] == "rgb" and rgb is None:
                rgb = {"id": row["id"], "name": row["filename"]}
            elif row["kind"] == "preview" and preview is None:
                preview = {"id": row["id"], "name": row["filename"]}
            other_meta = other_meta or meta
        meta0 = band_meta or other_meta  # bands carry position/gimbal; RGB XMP may not
        layers = [k for k, (_, need, _) in INDICES.items() if all(b in bands for b in need)]
        layers += [f"band_{BAND_KEYS[b]}" for b in BANDS if b in bands]
        irr = [b["irradiance"] for b in bands.values() if b["irradiance"] is not None]
        warnings = []
        if len(bands) < 4:
            warnings.append("Nicht alle vier Bänder im Index: " + ", ".join(
                b for b in BANDS if b not in bands) + " fehlt.")
        if irr and min(irr) <= 1.0:
            warnings.append("Sonnenlichtsensor ohne Messwert (Irradiance ≤ 1, z. B. Innenaufnahme): "
                            "Reflexions- und Indexberechnung gesperrt.")
        if any(b["irradiance"] is None for b in bands.values()):
            warnings.append("Einstrahlungswert fehlt: betroffene Bänder können nicht berechnet werden.")
        if any(b["sunlight_sensor_status"] not in (1, 2) for b in bands.values()):
            warnings.append("Sonnenlichtsensor ungültig oder Status fehlt: betroffene Bänder können nicht berechnet werden.")
        return {
            "capture_uuid": uuid, "source_key": PROCESSING_VERSION + "|" + "|".join(sorted(sources)), "optics": optics,
            "captured_at": meta0 and meta0.get("captured_at"),
            "model": meta0 and meta0.get("model"), "position": meta0 and meta0.get("position"),
            "gimbal": meta0 and meta0.get("gimbal"),
            "bands": bands, "rgb": rgb, "preview": preview, "layers": layers, "warnings": warnings,
        }


# -------------------------------------------------------------- service ----

class MultispectralService:
    CACHE_BANDS = 8
    COMPUTE_WAIT_SECONDS = 60

    def __init__(self, media_index: DjiMediaIndex, *, settings_factory=None, client_factory=None):
        from .minio_media_index import MinioMediaSettings, minio_client
        self.media = media_index
        self.catalog = MultispectralCatalog(media_index)
        self._settings_factory = settings_factory or MinioMediaSettings.from_env
        self._client_factory = client_factory or minio_client
        self._lock = threading.Lock()
        # Shared with other service instances, the media-sync process and TSDK.
        self._compute = ProcessingSlot()
        self._bands: OrderedDict = OrderedDict()
        self.summary_failures: list[str] = []

    def _band(self, band_id: str, scale: int):
        record = self.media.get(band_id)
        if record is None:
            raise MultispectralNotFound("Band not indexed")
        key = (record["id"], record["etag"], scale)
        cached = self._cached(key)
        if cached is not None:
            return cached
        if not self._compute.acquire(timeout=self.COMPUTE_WAIT_SECONDS):
            raise MultispectralBusy("Multispectral processing busy; retry shortly")
        try:
            cached = self._cached(key)  # filled by the request we waited for
            if cached is not None:
                return cached
            from .minio_media_index import read_indexed_object
            try:
                settings = self._settings_factory()
                data = read_indexed_object(record, settings, self._client_factory(settings),
                                           max_bytes=MAX_BAND_BYTES)
            except DjiMediaError:
                raise
            except Exception as exc:
                raise DjiMediaError("MinIO object unavailable") from exc
            dn, info = read_band(data)
            cal = (band_metadata(info["xmp"]).get("calibration") or {})
            grid = rectify(relative_reflectance(dn, info, cal), cal, scale=scale)
            # Publish the cache entry before releasing the processing slot so
            # the next waiter cannot start a duplicate decode.
            with self._lock:
                self._bands[key] = grid
                while len(self._bands) > self.CACHE_BANDS:
                    self._bands.popitem(last=False)
            return grid
        finally:
            self._compute.release()

    def _cached(self, key):
        with self._lock:
            if key in self._bands:
                self._bands.move_to_end(key)
                return self._bands[key]
        return None

    def layer(self, capture_uuid: str, layer: str, *, scale: int = 2):
        if layer not in LAYERS:
            raise MultispectralError("Unknown layer")
        if scale not in (1, 2, 4):
            raise MultispectralError("scale must be 1, 2 or 4")
        capture = self.catalog.capture(capture_uuid)
        if layer not in capture["layers"]:
            raise MultispectralError("Bands for this layer are missing in this capture")
        needed = ((({v: k for k, v in BAND_KEYS.items()}[layer[5:]],) if layer.startswith("band_")
                   else INDICES[layer][1]))
        bands = {name: self._band(capture["bands"][name]["id"], scale) for name in needed}
        grid = compute_layer(layer, bands)
        return capture, grid

    def analysis(self, capture_uuid: str, layer: str, *, scale: int = 2) -> dict:
        capture, grid = self.layer(capture_uuid, layer, scale=scale)
        label, _, formula = INDICES.get(layer, (None, None, None))
        stats = layer_stats(layer, grid)
        if layer == "ndvi":  # remembered for the map overview (local cache only)
            try:
                self.catalog.store_summary(capture_uuid, capture["source_key"], layer, stats)
            except (DjiMediaError, OSError, sqlite3.Error):
                pass
        return {
            "capture": capture, "layer": layer,
            "label": label or "Relative Reflexion " + layer[5:].upper(),
            "formula": formula, "width": int(grid.shape[1]), "height": int(grid.shape[0]),
            "scale": scale, "stats": stats,
            "method": "DJI Mavic 3M Image Processing Guide v1.0: Schwarzwert, Gain, Belichtung, "
                      "Vignettierung, Entzerrung, HMatrix-Ausrichtung, Sonnenlichtsensor",
            "relative": "Reflexion relativ (gemeinsamer Faktor ρ_NIR unbekannt); "
                        "normierte Indizes nach Gl. 6 davon unabhängig",
        }


    def stack_geotiff(self, capture_uuid: str, *, product: str = "reflectance", scale: int = 1,
                      refine: bool = True, georef: bool = True) -> tuple[bytes, dict]:
        """4-band GeoTIFF (NIR, G, R, RE) of one capture, see m3m_stack."""
        from .m3m_stack import BAND_ORDER, stack_bands, stack_to_geotiff
        from .minio_media_index import read_indexed_object
        capture = self.catalog.capture(capture_uuid)
        missing = [b for b in BAND_ORDER if b not in capture["bands"]]
        if missing:
            raise MultispectralError("Bands missing: " + ", ".join(missing))
        if not self._compute.acquire(timeout=self.COMPUTE_WAIT_SECONDS):
            raise MultispectralBusy("Multispectral processing busy; retry shortly")
        try:
            files = {}
            for name in BAND_ORDER:
                record = self.media.get(capture["bands"][name]["id"])
                if record is None:
                    raise MultispectralNotFound("Band not indexed")
                try:
                    settings = self._settings_factory()
                    files[name] = read_indexed_object(record, settings, self._client_factory(settings),
                                                      max_bytes=MAX_BAND_BYTES)
                except DjiMediaError:
                    raise
                except Exception as exc:
                    raise DjiMediaError("MinIO object unavailable") from exc
            result = stack_bands(files, product=product, scale=scale, refine=refine)
            data = stack_to_geotiff(result, georef=georef)
        finally:
            self._compute.release()
        info = {k: result[k] for k in ("product", "scale", "crop", "shifts", "capture_uuid")}
        return data, info

    def map_items(self) -> dict:
        """Capture positions, footprints/view cones and cached NDVI summaries."""
        from .thermal_geo import ground_footprint, view_cone
        summaries = self.catalog.summaries()
        items, missing = [], 0
        for c in self.catalog.captures():
            pos = c["position"]
            if not pos:
                missing += 1
                continue
            optics = c["optics"] or {}
            hfov, vfov = optics.get("hfov_deg"), optics.get("vfov_deg")
            foot = ground_footprint(pos, c["gimbal"], hfov, vfov, account_for_pitch=True) if hfov else None
            height = pos.get("relative_altitude_m")
            tilt = math.radians((c["gimbal"] or {}).get("pitch_deg", -90) + 90) if foot else 0
            gsd = (height / optics["focal_length_px"] / math.cos(tilt) ** 2 * 100
                   if foot and optics.get("focal_length_px") else None)
            cached = summaries.get(c["capture_uuid"])
            ndvi = cached[1] if cached and cached[0] == c["source_key"] else None
            items.append({
                "capture_uuid": c["capture_uuid"], "captured_at": c["captured_at"],
                "latitude": pos["latitude"], "longitude": pos["longitude"],
                "relative_altitude_m": height, "gps_status": pos.get("gps_status"),
                "gimbal_pitch_deg": (c["gimbal"] or {}).get("pitch_deg"),
                "gimbal_yaw_deg": (c["gimbal"] or {}).get("yaw_deg"),
                "footprint": foot,
                "view_cone": None if foot or not hfov else view_cone(pos, c["gimbal"], hfov),
                "ground_sample_cm": round(gsd, 2) if gsd else None,
                "has_ndvi": "ndvi" in c["layers"],
                "ndvi": None if ndvi is None else {k: ndvi.get(k) for k in
                                                   ("median", "mean", "p05", "p95", "classes")},
            })
        return {"items": items, "without_position": missing,
                "assumption": "Footprint nur bei Nadir-Aufnahmen; ebenes Gelände auf Startpunkthöhe"}

    def compute_missing_summaries(self, *, scale: int = 4) -> int:
        done = 0
        self.summary_failures = []
        for item in self.map_items()["items"]:
            if item["has_ndvi"] and item["ndvi"] is None:
                try:
                    self.analysis(item["capture_uuid"], "ndvi", scale=scale)
                except (MultispectralError, DjiMediaError):
                    self.summary_failures.append(item["capture_uuid"])
                    continue
                done += 1
        return done


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only M3M multispectral catalogue (range-reads headers, no MinIO writes)")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--ndvi", action="store_true",
                        help="also compute missing NDVI summaries for the map (reads band files)")
    args = parser.parse_args(argv)
    try:
        from dotenv import load_dotenv
        from .minio_media_index import MinioMediaSettings, minio_client
        if args.env_file:
            load_dotenv(args.env_file, override=False)
        settings = MinioMediaSettings.from_env()
        report = MultispectralCatalog(DjiMediaIndex()).scan(minio_client(settings), settings.bucket)
        if args.ndvi:
            service = MultispectralService(DjiMediaIndex())
            report["ndvi_summaries"] = service.compute_missing_summaries()
            report["ndvi_failed"] = len(service.summary_failures)
        print(json.dumps(report))
        return 1 if report["failed"] or report.get("ndvi_failed") else 0
    except (MultispectralError, DjiMediaError, OSError, sqlite3.Error) as exc:
        print("Multispectral catalogue error: " + str(exc).split("\n", 1)[0], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

