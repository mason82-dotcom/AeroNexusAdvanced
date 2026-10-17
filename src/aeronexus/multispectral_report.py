"""Bounded series statistics using the existing DJI-calibrated layer service.

Each capture remains separate: overlapping images must not be interpreted as
independent field area. No image normalization, radiometry or index formulas
are duplicated here.
"""
from datetime import datetime, timezone
import csv
from io import StringIO
import sqlite3

from .minio_media_index import DjiMediaChanged, DjiMediaError
from .multispectral import INDICES, PROCESSING_VERSION, MultispectralBusy, MultispectralError, _np


def summarize(grid, ndvi=None, *, threshold=None, bins=32):
    """Population statistics and an exact-count histogram; empty masks are valid."""
    np = _np()
    valid = np.isfinite(grid)
    valid_pixels = int(valid.sum())
    if threshold is not None:
        if ndvi is None or ndvi.shape != grid.shape:
            raise MultispectralError("NDVI mask raster dimensions differ")
        valid &= np.isfinite(ndvi) & (ndvi >= threshold)
    values = grid[valid].astype(np.float64)
    result = {"pixels": int(grid.size), "valid_pixels": valid_pixels,
              "selected_pixels": int(values.size),
              "selected_share": float(values.size / valid_pixels) if valid_pixels else None}
    names = ("min", "p05", "p10", "median", "p90", "p95", "max")
    result.update(dict.fromkeys((*names, "mean", "std")))
    histogram = {"edges": [], "counts": []}
    if values.size:
        result.update(zip(names, map(float, np.percentile(values, [0, 5, 10, 50, 90, 95, 100]))))
        result.update(mean=float(values.mean()), std=float(values.std()))
        counts, edges = np.histogram(values, bins=bins)
        histogram = {"edges": edges.tolist(), "counts": counts.tolist()}
    return result, histogram


def build_report(service, capture_uuids, layers, *, scale=4, threshold=None):
    """Process sequentially, preserving partial errors without leaking storage data."""
    if (not 1 <= len(capture_uuids) <= 20 or len(set(capture_uuids)) != len(capture_uuids)
            or not 1 <= len(layers) <= 4 or len(set(layers)) != len(layers)
            or any(layer not in INDICES for layer in layers) or scale not in (1, 2, 4)):
        raise MultispectralError("Select 1–20 distinct captures and 1–4 distinct indices; scale 1, 2 or 4")
    if threshold is not None and not -1 <= threshold <= 1:
        raise MultispectralError("NDVI threshold must be between -1 and 1")
    rows = []
    errors = (MultispectralError, DjiMediaError, OSError, sqlite3.Error)
    for uuid in capture_uuids:
        capture_rows = []
        capture = None
        try:
            capture = service.catalog.capture(uuid)
            service.catalog.assert_current(capture)
            ndvi = None
            if threshold is not None:
                mask_capture, ndvi = service.layer(uuid, "ndvi", scale=scale)
                if mask_capture["source_key"] != capture["source_key"]:
                    raise DjiMediaChanged("Capture changed")
            for layer in layers:
                row = {"capture_uuid": uuid, "captured_at": capture.get("captured_at"),
                       "layer": layer, "warnings": capture.get("warnings", [])}
                try:
                    source, grid = service.layer(uuid, layer, scale=scale)
                    if source["source_key"] != capture["source_key"]:
                        raise DjiMediaChanged("Capture changed")
                    stats, histogram = summarize(grid, ndvi, threshold=threshold)
                    row.update(status="ok" if stats["selected_pixels"] else "empty",
                               stats=stats, histogram=histogram)
                except DjiMediaChanged:
                    raise
                except errors as exc:
                    busy = isinstance(exc, MultispectralBusy)
                    row.update(status="error", code="processing_busy" if busy else "layer_unavailable",
                               message=("Verarbeitung ausgelastet. Erneut versuchen." if busy else
                                        "Ebene nicht berechenbar. Bänder und Kalibrierung prüfen."))
                capture_rows.append(row)
            # Do not mix a changing capture with an older mask or layer.
            if service.catalog.capture(uuid)["source_key"] != capture["source_key"]:
                raise DjiMediaChanged("Capture changed")
            service.catalog.assert_current(capture)
        except errors as exc:
            changed = isinstance(exc, DjiMediaChanged)
            busy = isinstance(exc, MultispectralBusy)
            capture_rows = [{"capture_uuid": uuid,
                             "captured_at": capture.get("captured_at") if capture else None,
                             "layer": layer, "status": "error",
                             "code": "source_changed" if changed else "processing_busy" if busy else "capture_unavailable",
                             "message": ("Quelldaten geändert. Katalog aktualisieren und erneut berechnen."
                                         if changed else "Verarbeitung ausgelastet. Erneut versuchen." if busy else
                                         "Aufnahme oder NDVI-Maske nicht berechenbar. Bänder und Kalibrierung prüfen."),
                             "warnings": capture.get("warnings", []) if capture else []}
                            for layer in layers]
        rows.extend(capture_rows)
    return {"generated_at": datetime.now(timezone.utc).isoformat(),
            "processing_version": PROCESSING_VERSION, "scale": scale,
            "ndvi_threshold": threshold, "capture_uuids": list(capture_uuids),
            "layers": list(layers), "rows": rows,
            "note": "Statistik je Aufnahme; überlappende Bilder werden nicht als Feldfläche summiert. "
                    "NDVI-Schwellen sind Richtwerte, keine Krankheitsdiagnose."}


CSV_FIELDS = ("capture_uuid", "captured_at", "layer", "status", "code", "scale", "ndvi_threshold",
              "pixels", "valid_pixels", "selected_pixels", "selected_share",
              "min", "p05", "p10", "median", "p90", "p95", "max", "mean", "std")


def report_csv(report):
    """Spreadsheet-friendly CSV with explicit settings and safe text cells."""
    out = StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=CSV_FIELDS, delimiter=";", extrasaction="ignore")
    writer.writeheader()
    for row in report["rows"]:
        values = {**row, **row.get("stats", {}), "scale": report["scale"],
                  "ndvi_threshold": report["ndvi_threshold"]}
        for key, value in values.items():
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                values[key] = "'" + value
        writer.writerow(values)
    return "\ufeff" + out.getvalue()
