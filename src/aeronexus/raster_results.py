"""Private local GeoTIFF/COG catalogue and bounded, read-only XYZ rendering.

Only files directly inside the configured results directory are admitted.
No remote URLs, VRT sources, uploads, source writes or automatic conversion.
Rasterio and NumPy are optional; importing the gateway never requires them.
"""
from collections import OrderedDict
from contextlib import contextmanager
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import struct
import threading
import zlib

from .studio_workspace import Workspace, now_utc


MAX_FILES = 500
MAX_FILE_BYTES = 64 * 1024**3
TILE_SIZE = 256
MERCATOR_LIMIT = 20037508.342789244
MAX_LAT = 85.05112878
_ID = re.compile(r"[0-9a-f]{32}\Z")
_render_slots = threading.BoundedSemaphore(2)
_scan_slot = threading.BoundedSemaphore(1)
_cache_lock = threading.Lock()
_tiles: OrderedDict = OrderedDict()
_stats: OrderedDict = OrderedDict()
_CACHE_BYTES = 16 * 1024**2
PALETTES = {
    "gray": ((0, 0, 0), (255, 255, 255)),
    "rdylgn": ((165, 0, 38), (244, 109, 67), (255, 255, 191), (102, 189, 99), (0, 104, 55)),
    "viridis": ((68, 1, 84), (59, 82, 139), (33, 145, 140), (94, 201, 98), (253, 231, 37)),
    "terrain": ((30, 90, 65), (125, 160, 90), (205, 190, 145), (155, 125, 100), (245, 245, 245)),
}


class RasterError(ValueError):
    pass


class RasterUnavailable(RasterError):
    pass


class RasterNotFound(RasterError):
    pass


class RasterChanged(RasterError):
    pass


class RasterBusy(RasterError):
    pass


def _libraries():
    try:
        import numpy as np
        import rasterio
    except (ImportError, OSError) as exc:
        raise RasterUnavailable("Rasterpaket fehlt oder ist nicht lauffähig: pip install -e '.[raster]'.") from exc
    return np, rasterio


@contextmanager
def _environment():
    _, rio = _libraries()
    # Do not create .aux.xml, inspect adjacent files, or fetch missing CRS grids.
    with rio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_PAM_ENABLED="NO",
                 PROJ_NETWORK="OFF", GDAL_NUM_THREADS="1", GDAL_CACHEMAX=32 * 1024**2):
        yield rio


def _version(path: Path) -> str:
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise RasterNotFound("Ergebnisdatei fehlt; Katalog aktualisieren.") from exc
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_FILE_BYTES:
        raise RasterError("Nur reguläre lokale Dateien bis 64 GiB sind erlaubt; keine Verknüpfungen.")
    signature = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    return sha256(repr(signature).encode()).hexdigest()[:24]


def tile_bounds(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    if not 0 <= z <= 22 or not 0 <= x < 2**z or not 0 <= y < 2**z:
        raise RasterError("Ungültige XYZ-Kachelkoordinaten (Zoom 0–22).")
    span = 2 * MERCATOR_LIMIT / 2**z
    left = -MERCATOR_LIMIT + x * span
    top = MERCATOR_LIMIT - y * span
    return left, top - span, left + span, top


def rgba_png(rgba) -> bytes:
    """Encode one bounded 8-bit RGBA tile, without a Pillow dependency."""
    height, width, channels = rgba.shape
    if channels != 4 or height != TILE_SIZE or width != TILE_SIZE:
        raise RasterError("Ungültige Kachelgröße.")

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)

    raw = b"".join(b"\x00" + row.tobytes() for row in rgba)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 3)) + chunk(b"IEND", b""))


def _range(low: float, high: float) -> None:
    if not all(math.isfinite(v) and abs(v) <= 1e15 for v in (low, high)) or high <= low:
        raise RasterError("Farbskala benötigt endliche Werte mit Obergrenze größer als Untergrenze.")


def inspect_raster(path: Path) -> dict:
    np, _ = _libraries()
    with _environment() as rio:
        from rasterio.enums import ColorInterp
        from rasterio.warp import transform_bounds

        with rio.open(path, driver="GTiff", sharing=False) as src:
            if src.driver != "GTiff" or src.crs is None:
                raise RasterError("GeoTIFF benötigt ein angegebenes Koordinatensystem.")
            if not (1 <= src.count <= 16 and 1 <= src.width <= 500000 and 1 <= src.height <= 500000):
                raise RasterError("Rastergröße oder Bandanzahl außerhalb der unterstützten Grenzen.")
            if abs(src.transform.determinant) < 1e-20 or src.gcps[0] or src.rpcs:
                raise RasterError("Eine gültige affine Georeferenzierung ist erforderlich; GCP/RPC werden nicht unterstützt.")
            if any(np.dtype(t).kind not in "uif" for t in src.dtypes):
                raise RasterError("Nur reelle numerische Rasterbänder werden unterstützt.")
            if any(h * w * np.dtype(t).itemsize > 64 * 1024**2
                   for (h, w), t in zip(src.block_shapes, src.dtypes)):
                raise RasterError("Rasterblöcke zu groß; als gekacheltes GeoTIFF/COG bereitstellen.")
            bounds = list(transform_bounds(src.crs, "EPSG:4326", *src.bounds, densify_pts=21))
            west, south, east, north = bounds
            if (not all(math.isfinite(v) for v in bounds) or not -180 <= west < east <= 180
                    or east - west > 180 or not -MAX_LAT <= south < north <= MAX_LAT):
                raise RasterError("Rasterausdehnung ist für diesen Web-Mercator-Viewer nicht unterstützt.")
            rgb = [src.colorinterp.index(c) + 1 for c in (ColorInterp.red, ColorInterp.green, ColorInterp.blue)
                   if c in src.colorinterp]
            if len(rgb) != 3:
                rgb = []
            bands = []
            for i in range(src.count):
                scale, offset = float(src.scales[i]), float(src.offsets[i])
                if not math.isfinite(scale) or not math.isfinite(offset):
                    raise RasterError("Ungültige Bandskalierung.")
                nodata = src.nodatavals[i]
                bands.append({"index": i + 1, "name": (src.descriptions[i] or f"Band {i + 1}")[:120],
                              "dtype": src.dtypes[i], "unit": (src.units[i] or "")[:40],
                              "scale": scale, "offset": offset,
                              "nodata": str(nodata) if nodata is not None and not math.isfinite(nodata) else nodata,
                              "overviews": src.overviews(i + 1)})
            kind = next((k for k in ("ndvi", "gndvi", "ndre", "lci", "dsm", "dtm")
                         if re.search(r"(?:^|[_\- ])" + k + r"(?:$|[_\- ])", path.stem.lower())),
                        "rgb" if rgb else "raster")
            cog = src.tags(ns="IMAGE_STRUCTURE").get("LAYOUT") == "COG"
            warnings = []
            if not cog:
                warnings.append("GeoTIFF ohne COG-Kennzeichnung; keine vollständige COG-Konformitätsprüfung.")
            if not bands[0]["overviews"] and src.width * src.height > 4_000_000:
                warnings.append("Interne Übersichten fehlen; kleine Zoomstufen und Stichproben können langsam sein.")
            return {"title": path.stem[:120], "filename": path.name, "kind": kind,
                    "width": src.width, "height": src.height, "bands": bands,
                    "crs": src.crs.to_string(), "bounds": bounds, "rgb_bands": rgb,
                    "cog": cog, "tiled": src.profile.get("tiled", False), "warnings": warnings,
                    "size_bytes": path.stat().st_size}


class RasterResults:
    def __init__(self, root: Path | None = None, source: Path | None = None):
        self.root = Workspace(root).root
        self.path = self.root / "raster-results.sqlite3"
        configured = source or Path(os.environ.get("AERONEXUS_RESULTS_DIR", str(self.root / "results")))
        configured = configured.expanduser()
        if configured.is_symlink():
            raise RasterError("Ergebnisordner muss ein reales Verzeichnis sein; Zielpfad direkt konfigurieren.")
        self.source = configured.resolve()
        self.source_id = sha256(str(self.source).encode()).hexdigest()

    @contextmanager
    def _connect(self, *, write=False):
        if self.path.is_symlink():
            raise RasterError("Ungültiger Ergebniskatalog.")
        if not self.path.exists():
            if not write:
                yield None
                return
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
            os.close(fd)
        if not self.path.is_file() or self.path.stat().st_mode & 0o077:
            raise RasterError("Ergebniskatalog muss eine private Datei mit Modus 0600 sein.")
        conn = sqlite3.connect(str(self.path) if write else f"file:{self.path}?mode=ro", uri=not write, timeout=15)
        conn.row_factory = sqlite3.Row
        try:
            if write:
                conn.execute("CREATE TABLE IF NOT EXISTS products (id TEXT PRIMARY KEY, source TEXT, metadata TEXT)")
                conn.execute("CREATE TABLE IF NOT EXISTS scans (source TEXT PRIMARY KEY, scanned_at TEXT)")
            yield conn
            if write:
                conn.commit()
        except Exception:
            if write:
                conn.rollback()
            raise
        finally:
            conn.close()

    def list(self, *, query="", limit=50, offset=0) -> dict:
        if not 1 <= limit <= 100 or offset < 0 or len(query) > 120:
            raise RasterError("Ungültige Katalogabfrage.")
        with self._connect() as db:
            items, scanned = [], None
            if db:
                scanned_row = db.execute("SELECT scanned_at FROM scans WHERE source=?", (self.source_id,)).fetchone()
                scanned = scanned_row[0] if scanned_row else None
                for row in db.execute("SELECT metadata FROM products WHERE source=?", (self.source_id,)):
                    item = json.loads(row[0])
                    if query.casefold() in item["filename"].casefold():
                        items.append(item)
        items.sort(key=lambda item: item["filename"].casefold())
        offset = min(offset, ((max(1, len(items)) - 1) // limit) * limit)
        return {"items": items[offset:offset + limit], "total": len(items), "limit": limit,
                "offset": offset, "scanned_at": scanned}

    def get(self, item_id: str, version: str | None = None) -> tuple[dict, Path]:
        if not _ID.fullmatch(item_id):
            raise RasterNotFound("Ergebnis nicht gefunden.")
        with self._connect() as db:
            row = db.execute("SELECT metadata FROM products WHERE source=? AND id=?",
                             (self.source_id, item_id)).fetchone() if db else None
        if row is None:
            raise RasterNotFound("Ergebnis nicht gefunden.")
        item = json.loads(row[0])
        name = item["filename"]
        if Path(name).name != name or "/" in name or "\\" in name:
            raise RasterError("Ungültiger Katalogeintrag.")
        path = self.source / name
        if (version is not None and version != item["version"]) or _version(path) != item["version"]:
            raise RasterChanged("Ergebnisdatei geändert; Katalog aktualisieren und Ergebnis erneut wählen.")
        return item, path

    def scan(self) -> dict:
        _libraries()
        if not self.source.is_dir():
            raise RasterError("Ergebnisordner fehlt. GeoTIFFs im konfigurierten Ergebnisordner bereitstellen.")
        if not _scan_slot.acquire(blocking=False):
            raise RasterBusy("Eine Katalogaktualisierung läuft bereits.")
        try:
            files = []
            for path in self.source.iterdir():
                if path.suffix.lower() in (".tif", ".tiff"):
                    files.append(path)
                    if len(files) > MAX_FILES:
                        raise RasterError("Maximal 500 Ergebnisdateien je Ordner; vorheriger Katalog bleibt erhalten.")
            items, errors = [], []
            for path in sorted(files):
                try:
                    version = _version(path)
                    item = inspect_raster(path)
                    if version != _version(path):
                        raise RasterChanged("Datei während des Einlesens geändert.")
                    item.update(id=sha256((self.source_id + "/" + path.name).encode()).hexdigest()[:32],
                                version=version, indexed_at=now_utc())
                    items.append(item)
                except (RasterError, OSError) as exc:
                    errors.append({"filename": path.name, "message": str(exc) if isinstance(exc, RasterError)
                                   else "Datei konnte nicht gelesen werden."})
                except Exception:
                    errors.append({"filename": path.name, "message": "Ungültiges oder nicht unterstütztes GeoTIFF."})
            scanned = now_utc()
            with self._connect(write=True) as db:
                db.execute("DELETE FROM products WHERE source=?", (self.source_id,))
                db.executemany("INSERT INTO products VALUES (?,?,?)",
                               [(i["id"], self.source_id, json.dumps(i, allow_nan=False)) for i in items])
                db.execute("INSERT OR REPLACE INTO scans VALUES (?,?)", (self.source_id, scanned))
            return {"indexed": len(items), "rejected": len(errors), "errors": errors[:50], "scanned_at": scanned}
        finally:
            _scan_slot.release()

    def statistics(self, item_id: str, band: int = 1, version: str | None = None) -> dict:
        item, path = self.get(item_id, version)
        if not 1 <= band <= len(item["bands"]):
            raise RasterError("Band nicht vorhanden.")
        key = (str(path), item["version"], band)
        with _cache_lock:
            if key in _stats:
                _stats.move_to_end(key)
                return _stats[key]
        if not _render_slots.acquire(timeout=5):
            raise RasterBusy("Rasterverarbeitung ausgelastet; erneut versuchen.")
        try:
            np, _ = _libraries()
            with _environment() as rio, rio.open(path, driver="GTiff", sharing=False) as src:
                arr = src.read(band, out_shape=(min(256, src.height), min(256, src.width)), masked=True).astype("float64")
                arr = arr * item["bands"][band - 1]["scale"] + item["bands"][band - 1]["offset"]
                values = arr.compressed()
                values = values[np.isfinite(values)]
                if not values.size:
                    raise RasterError("Das gewählte Band enthält keine gültigen Stichprobenwerte.")
                lo, hi = (float(v) for v in np.percentile(values, [2, 98]))
                if lo == hi:
                    delta = max(abs(lo) * .01, .5)
                    lo, hi = lo - delta, hi + delta
                result = {"band": band, "min": float(values.min()), "max": float(values.max()),
                          "p02": lo, "p98": hi, "sample_count": int(values.size), "approximate": True}
            self.get(item_id, item["version"])
            with _cache_lock:
                _stats[key] = result
                while len(_stats) > 64:
                    _stats.popitem(last=False)
            return result
        finally:
            _render_slots.release()

    def tile(self, item_id: str, z: int, x: int, y: int, *, band=1, mode="scalar",
             palette="viridis", low=0., high=1., version: str | None = None) -> bytes:
        bounds = tile_bounds(z, x, y)
        _range(low, high)
        if palette not in PALETTES or mode not in ("scalar", "rgb"):
            raise RasterError("Unbekannte Darstellung oder Farbpalette.")
        item, path = self.get(item_id, version)
        if not 1 <= band <= len(item["bands"]):
            raise RasterError("Band nicht vorhanden.")
        if mode == "rgb" and not item["rgb_bands"]:
            raise RasterError("Keine ausdrücklich gekennzeichneten RGB-Bänder vorhanden.")
        key = (str(path), item["version"], z, x, y, band, mode, palette, low, high)
        with _cache_lock:
            if key in _tiles:
                _tiles.move_to_end(key)
                return _tiles[key]
        if not _render_slots.acquire(timeout=5):
            raise RasterBusy("Rasterverarbeitung ausgelastet; erneut versuchen.")
        try:
            np, _ = _libraries()
            from rasterio.enums import ColorInterp, Resampling
            from rasterio.transform import from_bounds
            from rasterio.vrt import WarpedVRT

            indexes = item["rgb_bands"] if mode == "rgb" else [band]
            with _environment() as rio, rio.open(path, driver="GTiff", sharing=False) as src:
                # Alpha explicitly represents coverage even when zero is valid data.
                with WarpedVRT(src, crs="EPSG:3857", transform=from_bounds(*bounds, TILE_SIZE, TILE_SIZE),
                               width=TILE_SIZE, height=TILE_SIZE, dtype="float32", warp_mem_limit=32,
                               add_alpha=ColorInterp.alpha not in src.colorinterp,
                               resampling=Resampling.nearest) as vrt:
                    arr = vrt.read(indexes=indexes, masked=True).astype("float64")
                    valid = np.all(~np.ma.getmaskarray(arr), axis=0)
                    alpha = next((i + 1 for i, c in enumerate(vrt.colorinterp) if c == ColorInterp.alpha), None)
                    if alpha:
                        valid &= vrt.read(alpha) > 0
                    for i, b in enumerate(indexes):
                        arr[i] = arr[i] * item["bands"][b - 1]["scale"] + item["bands"][b - 1]["offset"]
                    valid &= np.all(np.isfinite(arr.data), axis=0)
                    values = np.nan_to_num(arr.filled(low), nan=low, posinf=high, neginf=low)
            rgba = np.zeros((TILE_SIZE, TILE_SIZE, 4), dtype="uint8")
            if mode == "rgb":
                rgba[:, :, :3] = np.moveaxis(np.clip((values - low) * 255 / (high - low), 0, 255).astype("uint8"), 0, 2)
            else:
                normalized = np.clip((values[0] - low) / (high - low), 0, 1)
                colors = PALETTES[palette]
                stops = np.linspace(0, 1, len(colors))
                for channel in range(3):
                    rgba[:, :, channel] = np.interp(normalized, stops, [c[channel] for c in colors]).astype("uint8")
            rgba[:, :, 3] = valid.astype("uint8") * 255
            png = rgba_png(rgba)
            self.get(item_id, item["version"])
            with _cache_lock:
                _tiles[key] = png
                while len(_tiles) > 128 or sum(len(v) for v in _tiles.values()) > _CACHE_BYTES:
                    _tiles.popitem(last=False)
            return png
        finally:
            _render_slots.release()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Lokale GeoTIFF-/COG-Ergebnisse registrieren; Quellen bleiben unverändert.")
    parser.parse_args()
    try:
        print(json.dumps(RasterResults().scan(), ensure_ascii=False, indent=2))
    except (RasterError, OSError, sqlite3.Error) as exc:
        parser.exit(1, f"Ergebniskatalog: {exc}\n")


if __name__ == "__main__":
    main()
