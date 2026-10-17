"""Stack the four DJI Mavic 3M bands into one 4-band GeoTIFF for QGIS.

Feature set follows mirrormapper/m3m-image-stacking (MIT): band order
NIR, Green, Red, RedEdge; vignetting, undistort and Calibrated HMatrix per
DJI's *Mavic 3M Image Processing Guide*; empty warp borders cropped; capture
tags (GPS, CaptureUUID) in the file. Re-implemented with numpy only (no
OpenCV/rasterio/GDAL) on top of ``multispectral``. Additions:

* ``product="reflectance"``: relative reflectance with the sunlight sensor
  (Eq. 4-6 of the guide, float32, NaN = no data) besides the DN product.
* DJI step 4 (residual alignment, e.g. different exposure times in flight):
  translation by phase correlation of edge images against NIR, applied only
  when the correlation peak is clear and the shift is small.
* Approximate georeference (EPSG:4326, affine ModelTransformation) for
  near-nadir captures from position, gimbal and the calibrated focal length
  over flat terrain - good for orientation in QGIS, not an orthomosaic.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import struct
import sys
from xml.sax.saxutils import escape
import zlib

from .multispectral import (MultispectralError, _np, _ms_optics, band_metadata, item_metadata,
                            read_band, rectify, relative_reflectance)

BAND_ORDER = ("NIR", "Green", "Red", "RedEdge")
PRODUCTS = ("reflectance", "dn")
TILE = 256
MAX_SHIFT_PX = 30          # at full resolution; larger shifts are treated as unreliable
MIN_CONFIDENCE = 8.0       # correlation peak height in standard deviations
SOFTWARE = "AeroNexusAdvanced m3m_stack (after mirrormapper/m3m-image-stacking, MIT)"


# ------------------------------------------------------------ alignment ----

def _edges(image):
    np = _np()
    a = image.astype(np.float32)
    finite = np.isfinite(a)
    if not finite.any():
        raise MultispectralError("Band has no valid pixels")
    a = np.where(finite, a, np.float32(np.median(a[finite])))
    gy, gx = np.gradient(a)
    m = np.hypot(gx, gy)
    m -= m.mean()
    h, w = m.shape
    return m * np.outer(np.hanning(h), np.hanning(w)).astype(np.float32)


def phase_shift(reference, moving, *, max_shift: float) -> tuple[float, float, float]:
    """Translation s=(dy, dx) with moving(y, x) ≈ reference(y - dy, x - dx),
    plus the peak strength in standard deviations of the correlation surface."""
    np = _np()
    if reference.shape != moving.shape:
        raise MultispectralError("Band raster dimensions differ")
    f = np.fft.rfft2(_edges(reference))
    g = np.fft.rfft2(_edges(moving))
    cross = g * np.conj(f)
    cross /= np.abs(cross) + 1e-12
    surface = np.fft.irfft2(cross, s=reference.shape)
    h, w = surface.shape
    py, px = np.unravel_index(int(np.argmax(surface)), surface.shape)
    peak = surface[py, px]
    confidence = float((peak - surface.mean()) / (surface.std() + 1e-12))

    def sub(c_minus, c0, c_plus):
        denom = c_minus - 2 * c0 + c_plus
        return 0.0 if abs(denom) < 1e-12 else 0.5 * (c_minus - c_plus) / denom
    dy = py + sub(surface[(py - 1) % h, px], peak, surface[(py + 1) % h, px])
    dx = px + sub(surface[py, (px - 1) % w], peak, surface[py, (px + 1) % w])
    dy = dy - h if dy > h / 2 else dy
    dx = dx - w if dx > w / 2 else dx
    if abs(dy) > max_shift or abs(dx) > max_shift:
        confidence = 0.0
    return float(dy), float(dx), confidence


def shift_image(image, dy: float, dx: float, *, block_rows: int = 256):
    """aligned(y, x) = image(y + dy, x + dx), bilinear; NaN outside (row blocks)."""
    np = _np()
    h, w = image.shape
    out = np.empty((h, w), dtype=np.float32)
    u = np.arange(w, dtype=np.float32) + np.float32(dx)
    x0 = np.clip(np.floor(u).astype(np.int64), 0, w - 2)
    fx = (u - x0)[None, :]
    col_ok = (u >= 0) & (u <= w - 1)
    for r0 in range(0, h, block_rows):
        r1 = min(h, r0 + block_rows)
        v = np.arange(r0, r1, dtype=np.float32) + np.float32(dy)
        y0 = np.clip(np.floor(v).astype(np.int64), 0, h - 2)
        fy = (v - y0)[:, None]
        top = image[y0][:, x0] * (1 - fx) + image[y0][:, x0 + 1] * fx
        bottom = image[y0 + 1][:, x0] * (1 - fx) + image[y0 + 1][:, x0 + 1] * fx
        block = top * (1 - fy) + bottom * fy
        block[~(((v >= 0) & (v <= h - 1))[:, None] & col_ok[None, :])] = np.nan
        out[r0:r1] = block
    return out


# --------------------------------------------------------------- stack ----

def _vignetted_dn(dn, cal: dict):
    """DN product as in m3m-image-stacking: vignetting applied to raw DN."""
    np = _np()
    out = dn.astype(np.float32)
    k = cal.get("vignetting")
    if k:
        h, w = dn.shape
        cx = cal.get("center_x") if cal.get("center_x") is not None else w / 2
        cy = cal.get("center_y") if cal.get("center_y") is not None else h / 2
        yy, xx = np.ogrid[0:h, 0:w]
        r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2, dtype=np.float32)
        poly, power = np.ones_like(r), np.ones_like(r)
        for coefficient in k:
            power *= r
            poly += np.float32(coefficient) * power
        out *= poly
    out[dn == 0] = np.nan
    return out


def stack_bands(band_files: dict[str, bytes], *, product: str = "reflectance", scale: int = 1,
                refine: bool = True, crop_margin: int = 50) -> dict:
    """band name -> TIFF bytes  =>  {"bands": float32 (4,H,W) in BAND_ORDER, ...}."""
    np = _np()
    if product not in PRODUCTS:
        raise MultispectralError("product must be reflectance or dn")
    if scale not in (1, 2, 4):
        raise MultispectralError("scale must be 1, 2 or 4")
    if not 0 <= crop_margin <= 500:
        raise MultispectralError("crop_margin must be between 0 and 500")
    missing = [b for b in BAND_ORDER if b not in band_files]
    if missing:
        raise MultispectralError("Bands missing: " + ", ".join(missing))
    grids, metas = {}, {}
    for name in BAND_ORDER:
        dn, info = read_band(band_files[name])
        meta = band_metadata(info["xmp"])
        if meta["band"] != name:
            raise MultispectralError(f"File for {name} contains band {meta['band']}")
        cal = meta.get("calibration") or {}
        values = relative_reflectance(dn, info, cal) if product == "reflectance" else _vignetted_dn(dn, cal)
        grids[name] = rectify(values, cal, scale=scale)
        metas[name] = meta
    uuids = {m["capture_uuid"] for m in metas.values()}
    if len(uuids) != 1:
        raise MultispectralError("Bands belong to different captures")
    shifts = {}
    if refine:
        # Correlate on at most ~1300 px wide images (half resolution for full-res
        # stacks): same accuracy for these shifts at a quarter of the FFT memory.
        step = 2 if scale == 1 else 1
        reference = grids["NIR"][::step, ::step]
        for name in BAND_ORDER[1:]:
            dy, dx, conf = phase_shift(reference, grids[name][::step, ::step],
                                       max_shift=MAX_SHIFT_PX / scale / step)
            dy, dx = dy * step, dx * step
            applied = conf >= MIN_CONFIDENCE and (abs(dy) > 0.05 or abs(dx) > 0.05)
            if applied:
                grids[name] = shift_image(grids[name], dy, dx)
            shifts[name] = {"dy_px": round(dy * scale, 2), "dx_px": round(dx * scale, 2),
                            "confidence": round(conf, 1), "applied": applied}
    cube = np.stack([grids[name] for name in BAND_ORDER])
    valid = np.isfinite(cube).all(axis=0)
    if not valid.any():
        raise MultispectralError("No common valid area of the four bands")
    rows, cols = np.where(valid)
    vy0, vy1, vx0, vx1 = int(rows.min()), int(rows.max()) + 1, int(cols.min()), int(cols.max()) + 1
    # Trim warp borders (mirrormapper default 50 px), at most 10 % per side.
    m = min(crop_margin // scale, (vy1 - vy0) // 10, (vx1 - vx0) // 10)
    y0, y1, x0, x1 = vy0 + m, vy1 - m, vx0 + m, vx1 - m
    if y1 - y0 < 8 or x1 - x0 < 8:
        raise MultispectralError("Crop margin leaves no image")
    nir = metas["NIR"]
    return {"bands": cube[:, y0:y1, x0:x1], "product": product, "scale": scale,
            "crop": {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0, "margin_px": m * scale},
            "shifts": shifts, "capture_uuid": nir["capture_uuid"], "captured_at": nir["captured_at"],
            "position": nir["position"], "gimbal": nir["gimbal"],
            "optics": _ms_optics(nir.get("calibration") or {})}


def georeference(result: dict) -> list[float] | None:
    """Affine ModelTransformation (16 doubles, lon/lat EPSG:4326) or None."""
    from .thermal_geo import ground_footprint
    optics = result.get("optics")
    if not optics or not result.get("position"):
        return None
    foot = ground_footprint(result["position"], result["gimbal"], optics["hfov_deg"],
                            optics["vfov_deg"], account_for_pitch=True)
    if foot is None:
        return None
    (lat_tl, lon_tl), (lat_tr, lon_tr), _, (lat_bl, lon_bl) = foot
    full_w, full_h = optics["width"], optics["height"]
    a, b = (lon_tr - lon_tl) / full_w, (lon_bl - lon_tl) / full_h   # lon per full-res col/row
    e, f = (lat_tr - lat_tl) / full_w, (lat_bl - lat_tl) / full_h   # lat per full-res col/row
    s, crop = result["scale"], result["crop"]
    ox, oy = crop["x"] * s, crop["y"] * s
    return [a * s, b * s, 0.0, lon_tl + a * ox + b * oy,
            e * s, f * s, 0.0, lat_tl + e * ox + f * oy,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]


# ------------------------------------------------------------- GeoTIFF ----

def write_geotiff(cube, *, descriptions: list[str], metadata: dict[str, str],
                  dtype: str = "float32", nodata: str | None = None,
                  transform: list[float] | None = None) -> bytes:
    """Little-endian tiled TIFF, planar (one tile set per band), Deflate.

    Readable by GDAL/QGIS: band descriptions and metadata in GDAL_METADATA,
    optional GDAL_NODATA, optional EPSG:4326 ModelTransformation + GeoKeys."""
    np = _np()
    bands, height, width = cube.shape
    if dtype == "uint16":
        data = np.nan_to_num(cube, nan=0).round().clip(0, 65535).astype("<u2")
        bits, fmt = 16, 1
    elif dtype == "float32":
        data, bits, fmt = cube.astype("<f4"), 32, 3
    else:
        raise MultispectralError("dtype must be uint16 or float32")
    tiles_x, tiles_y = -(-width // TILE), -(-height // TILE)
    body, offsets, counts = bytearray(), [], []
    start = 8
    for band in range(bands):
        for ty in range(tiles_y):
            for tx in range(tiles_x):
                tile = np.zeros((TILE, TILE), dtype=data.dtype)
                part = data[band, ty * TILE:(ty + 1) * TILE, tx * TILE:(tx + 1) * TILE]
                tile[:part.shape[0], :part.shape[1]] = part
                packed = zlib.compress(tile.tobytes(), 6)
                offsets.append(start + len(body))
                counts.append(len(packed))
                body += packed
                if len(body) % 2:
                    body += b"\0"
    items = "".join(f'<Item name="{escape(k)}">{escape(str(v))}</Item>' for k, v in metadata.items())
    items += "".join(f'<Item name="DESCRIPTION" sample="{i}" role="description">{escape(d)}</Item>'
                     for i, d in enumerate(descriptions))
    gdal_meta = f"<GDALMetadata>{items}</GDALMetadata>\0".encode("utf-8")
    entries = [  # (tag, type, values) ; 2=ASCII 3=SHORT 4=LONG 12=DOUBLE
        (256, 4, [width]), (257, 4, [height]), (258, 3, [bits] * bands), (259, 3, [8]),
        (262, 3, [1]), (277, 3, [bands]), (284, 3, [2]),
        (305, 2, (SOFTWARE + "\0").encode("ascii")),
        (322, 3, [TILE]), (323, 3, [TILE]), (324, 4, offsets), (325, 4, counts),
        (338, 3, [0] * (bands - 1)), (339, 3, [fmt] * bands),
    ]
    if transform is not None:
        entries += [(34264, 12, transform),
                    (34735, 3, [1, 1, 0, 3, 1024, 0, 1, 2, 1025, 0, 1, 1, 2048, 0, 1, 4326])]
    entries.append((42112, 2, gdal_meta))
    if nodata is not None:
        entries.append((42113, 2, (nodata + "\0").encode("ascii")))
    entries.sort(key=lambda e: e[0])
    ifd_offset = start + len(body)
    ifd_size = 2 + 12 * len(entries) + 4
    extra = bytearray()
    ifd = bytearray(struct.pack("<H", len(entries)))
    size_of = {2: 1, 3: 2, 4: 4, 12: 8}
    for tag, typ, values in entries:
        raw = (values if typ == 2 else
               struct.pack("<" + {3: "H", 4: "I", 12: "d"}[typ] * len(values), *values))
        count = len(values)
        if len(raw) <= 4:
            ifd += struct.pack("<HHI", tag, typ, count) + raw.ljust(4, b"\0")
        else:
            ifd += struct.pack("<HHII", tag, typ, count, ifd_offset + ifd_size + len(extra))
            extra += raw
            if len(extra) % 2:
                extra += b"\0"
        assert size_of[typ]  # supported types only
    ifd += struct.pack("<I", 0)
    return b"II*\0" + struct.pack("<I", ifd_offset) + bytes(body) + bytes(ifd) + bytes(extra)


def stack_to_geotiff(result: dict, *, georef: bool = True) -> bytes:
    position = result.get("position") or {}
    metadata = {
        "PROCESSING_SOFTWARE": "AeroNexusAdvanced m3m_stack",
        "BAND_ORDER": ",".join(BAND_ORDER),
        "PRODUCT": ("relative reflectance (DJI M3M guide Eq. 4-6)" if result["product"] == "reflectance"
                    else "DN with vignetting/undistort/alignment (not reflectance)"),
        "CORRECTIONS": "Vignetting+Distortion+HMatrixAlignment"
                       + ("+PhaseCorrelation" if any(s["applied"] for s in result["shifts"].values()) else ""),
        "RESIDUAL_SHIFTS": ";".join(f'{b}:{s["dy_px"]},{s["dx_px"]}{"" if s["applied"] else "(not applied)"}'
                                    for b, s in result["shifts"].items()) or "not computed",
        "DJI_CAPTURE_UUID": result["capture_uuid"] or "",
        "DJI_CAPTURED_AT": result["captured_at"] or "",
        "DJI_GPS_LATITUDE": position.get("latitude", ""),
        "DJI_GPS_LONGITUDE": position.get("longitude", ""),
        "DJI_RELATIVE_ALTITUDE": position.get("relative_altitude_m", ""),
        "SCALE": result["scale"],
    }
    transform = georeference(result) if georef else None
    metadata["GEOREFERENCE"] = ("approximate, nadir footprint over flat terrain (EPSG:4326)"
                                if transform else "none (not a nadir capture or no position)")
    reflectance = result["product"] == "reflectance"
    return write_geotiff(result["bands"], descriptions=list(BAND_ORDER), metadata=metadata,
                         dtype="float32" if reflectance else "uint16",
                         nodata="nan" if reflectance else None, transform=transform)


# ----------------------------------------------------------------- CLI ----

def find_captures(folder: Path) -> dict[str, dict[str, Path]]:
    """CaptureUUID -> {band: path} for local M3M TIFFs (header read only)."""
    captures: dict[str, dict[str, Path]] = {}
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.is_symlink() or path.suffix.lower() not in (".tif", ".tiff"):
            continue
        with path.open("rb") as handle:
            head = handle.read(256 * 1024)
        try:
            meta = item_metadata(path.name, head)
        except MultispectralError:
            meta = None
        if meta and meta["kind"] == "band":
            captures.setdefault(meta["capture_uuid"], {})[meta["band"]] = path
    return captures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stack DJI Mavic 3M G/R/RE/NIR TIFFs into a 4-band GeoTIFF (NIR, G, R, RE)")
    parser.add_argument("input", type=Path, help="folder with M3M *_MS_*.TIF files")
    parser.add_argument("-o", "--output", type=Path, default=Path("aligned_output"))
    parser.add_argument("--product", choices=PRODUCTS, default="reflectance")
    parser.add_argument("--scale", type=int, choices=(1, 2, 4), default=1)
    parser.add_argument("--crop-margin", type=int, default=50)
    parser.add_argument("--no-refine", action="store_true", help="skip phase-correlation alignment")
    parser.add_argument("--no-georef", action="store_true")
    parser.add_argument("--force", action="store_true", help="overwrite existing output files")
    args = parser.parse_args(argv)
    if not args.input.is_dir():
        parser.error(f"input folder does not exist: {args.input}")
    args.output.mkdir(parents=True, exist_ok=True)
    written = failed = 0
    for uuid, bands in find_captures(args.input).items():
        stem = (bands.get("NIR") or next(iter(bands.values()))).stem.replace("_MS_NIR", "")
        target = args.output / f"{stem}_{uuid[:8]}_aligned.tif"
        if len(bands) < 4:
            print(f"{stem}: incomplete capture, missing "
                  + ", ".join(b for b in BAND_ORDER if b not in bands), file=sys.stderr)
            continue
        if target.exists() and not args.force:
            print(f"{target.name}: exists (use --force)", file=sys.stderr)
            continue
        try:
            result = stack_bands({b: p.read_bytes() for b, p in bands.items()}, product=args.product,
                                 scale=args.scale, refine=not args.no_refine,
                                 crop_margin=args.crop_margin)
            target.write_bytes(stack_to_geotiff(result, georef=not args.no_georef))
            written += 1
            print(f"{target.name}: {result['crop']['width']}x{result['crop']['height']}x4, "
                  f"shifts {result['shifts'] or 'not computed'}")
        except (MultispectralError, OSError) as exc:
            failed += 1
            print(f"{stem}: {exc}", file=sys.stderr)
    print(f"{written} stacked TIFF(s) in {args.output}. Band 1 is NIR, not red.")
    return 1 if failed or not written else 0


if __name__ == "__main__":
    raise SystemExit(main())
