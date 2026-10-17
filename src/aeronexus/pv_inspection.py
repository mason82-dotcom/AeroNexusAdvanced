"""PV module inspection on DJI Thermal SDK temperature grids.

Orientation: IEC TS 62446-3:2017 (outdoor infrared thermography of PV
modules and plants). The standard is not reproduced here. Its evaluation
compares an abnormality with the temperature of normally working module
area and requires stable, sufficiently high irradiance. This module
implements that comparison with **configurable** guide values:

* reference = median temperature of the selected PV area (robust against
  the hot spots themselves),
* ΔT classes (default < 10 K / 10–20 K / > 20 K, the commonly used
  practitioner reading of IEC TS 62446-3) – check against the standard and
  the inspection contract before relying on them,
* measurement-condition checklist (irradiance ≥ 600 W/m², wind, cloud cover,
  viewing angle, geometric resolution).

The final class of abnormality and fault pattern remain the decision of a
qualified thermographer; pattern names here are geometric hints only.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import math


class PvInspectionError(ValueError):
    pass


def _check_range(name, value, low, high, *, optional=True):
    if value is None and optional:
        return None
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise PvInspectionError(f"{name} must be between {low:g} and {high:g}")
    return float(value)


@dataclass(frozen=True)
class PvThresholds:
    detect_k: float = 3.0      # pixels warmer than reference + detect_k form candidates
    class2_k: float = 10.0
    class3_k: float = 20.0
    min_pixels: int = 4
    cell_size_m: float = 0.166  # typical crystalline cell edge (M6..M10: 0.166..0.182 m)

    def __post_init__(self):
        _check_range("detect_k", self.detect_k, 0.5, 50, optional=False)
        _check_range("class2_k", self.class2_k, 1, 100, optional=False)
        _check_range("class3_k", self.class3_k, 1, 150, optional=False)
        _check_range("cell_size_m", self.cell_size_m, 0.05, 0.5, optional=False)
        if not self.detect_k <= self.class2_k < self.class3_k:
            raise PvInspectionError("Thresholds must satisfy detect_k <= class2_k < class3_k")
        if type(self.min_pixels) is not int or not 1 <= self.min_pixels <= 10000:
            raise PvInspectionError("min_pixels must be between 1 and 10000")


@dataclass(frozen=True)
class PvConditions:
    irradiance_wm2: float | None = None
    wind_kmh: float | None = None
    cloud_okta: float | None = None
    module_tilt_deg: float | None = None
    module_azimuth_deg: float | None = None  # direction the module faces, 0 = north

    def __post_init__(self):
        _check_range("irradiance_wm2", self.irradiance_wm2, 0, 1500)
        _check_range("wind_kmh", self.wind_kmh, 0, 200)
        _check_range("cloud_okta", self.cloud_okta, 0, 8)
        _check_range("module_tilt_deg", self.module_tilt_deg, 0, 90)
        _check_range("module_azimuth_deg", self.module_azimuth_deg, 0, 360)


@dataclass(frozen=True)
class Region:
    x: int
    y: int
    w: int
    h: int

    def clip(self, width: int, height: int) -> "Region":
        x0, y0 = max(0, self.x), max(0, self.y)
        x1, y1 = min(width, self.x + self.w), min(height, self.y + self.h)
        if x1 - x0 < 2 or y1 - y0 < 2:
            raise PvInspectionError("PV area is outside the image or too small")
        return Region(x0, y0, x1 - x0, y1 - y0)


CLASS_LABELS = {
    1: "Klasse 1 – beobachten (ΔT < Schwelle 2)",
    2: "Klasse 2 – Instandhaltung planen",
    3: "Klasse 3 – dringend prüfen (sicherheitsrelevant möglich)",
}


def _pattern(w: int, h: int, pixels: int, cell_px: float | None) -> str:
    if cell_px is None or cell_px <= 0:
        return "unbestimmt (keine Bodenauflösung)"
    long_side, short_side = max(w, h) / cell_px, min(w, h) / cell_px
    cells = pixels / (cell_px * cell_px)
    if cells < 0.5:
        return "punktueller Hotspot"
    if cells <= 1.6 and long_side <= 1.6:
        return "Einzelzelle"
    if short_side <= 1.6 and long_side >= 3:
        return "Zellstreifen (z. B. Substring/Bypass)"
    if cells <= 6:
        return "mehrere Zellen"
    return "großflächig (Modul/Modulgruppe)"


def inspect(width: int, height: int, grid, region: Region | None = None,
            thresholds: PvThresholds | None = None, *, ground_sample_m: float | None = None) -> dict:
    """Connected warm areas inside ``region`` relative to its median temperature."""
    thresholds = thresholds or PvThresholds()
    if width * height != len(grid) or width <= 1 or height <= 1:
        raise PvInspectionError("Temperature grid does not match its size")
    area = (region or Region(0, 0, width, height)).clip(width, height)
    values = sorted(grid[y * width + x] for y in range(area.y, area.y + area.h)
                    for x in range(area.x, area.x + area.w))
    n = len(values)
    reference = values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2
    spread = values[int(0.95 * (n - 1))] - values[int(0.05 * (n - 1))]
    limit = reference + thresholds.detect_k
    seen = bytearray(width * height)
    cell_px = (thresholds.cell_size_m / ground_sample_m) if ground_sample_m else None
    anomalies, total_px = [], 0
    for y in range(area.y, area.y + area.h):
        for x in range(area.x, area.x + area.w):
            start = y * width + x
            if seen[start] or grid[start] < limit:
                continue
            queue, members = deque([start]), []
            seen[start] = 1
            while queue:
                idx = queue.popleft()
                members.append(idx)
                cx, cy = idx % width, idx // width
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if area.x <= nx < area.x + area.w and area.y <= ny < area.y + area.h:
                        nidx = ny * width + nx
                        if not seen[nidx] and grid[nidx] >= limit:
                            seen[nidx] = 1
                            queue.append(nidx)
            if len(members) < thresholds.min_pixels:
                continue
            total_px += len(members)
            xs = [i % width for i in members]
            ys = [i // width for i in members]
            hot = max(members, key=grid.__getitem__)
            t_max = grid[hot]
            delta = t_max - reference
            klass = 3 if delta >= thresholds.class3_k else 2 if delta >= thresholds.class2_k else 1
            bw, bh = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
            anomalies.append({
                "x": min(xs), "y": min(ys), "w": bw, "h": bh, "pixels": len(members),
                "hot_x": hot % width, "hot_y": hot // width,
                "max_c": round(t_max, 2),
                "mean_c": round(math.fsum(grid[i] for i in members) / len(members), 2),
                "delta_k": round(delta, 2), "class": klass, "class_label": CLASS_LABELS[klass],
                "area_m2": round(len(members) * ground_sample_m ** 2, 4) if ground_sample_m else None,
                "pattern_hint": _pattern(bw, bh, len(members), cell_px),
            })
    anomalies.sort(key=lambda a: (-a["class"], -a["delta_k"]))
    counts = {k: sum(a["class"] == k for a in anomalies) for k in (1, 2, 3)}
    warnings = []
    if region is None:
        warnings.append("Gesamtes Bild ausgewertet: PV-Bereich markieren, damit Straßen, Dächer "
                        "oder Vegetation nicht als Anomalie zählen.")
    if total_px > 0.15 * area.w * area.h:
        warnings.append(f"{100 * total_px / (area.w * area.h):.0f} % des Bereichs sind auffällig: "
                        "Bereich enthält vermutlich Nicht-PV-Flächen, Referenz (Median) unsicher.")
    if cell_px is not None and cell_px < 3:
        warnings.append(f"Nur {cell_px:.1f} px je Zellkante: Einzelzell-Fehler sind nicht sicher "
                        "auflösbar (niedriger fliegen).")
    return {
        "region": {"x": area.x, "y": area.y, "w": area.w, "h": area.h},
        "reference_c": round(reference, 2), "reference_method": "Median des PV-Bereichs",
        "spread_p5_p95_k": round(spread, 2),
        "thresholds": {"detect_k": thresholds.detect_k, "class2_k": thresholds.class2_k,
                       "class3_k": thresholds.class3_k, "min_pixels": thresholds.min_pixels,
                       "cell_size_m": thresholds.cell_size_m},
        "cell_size_px": round(cell_px, 2) if cell_px else None,
        "anomalies": anomalies[:200], "anomaly_count": len(anomalies),
        "anomaly_pixels": total_px, "class_counts": counts,
        "worst_class": max((a["class"] for a in anomalies), default=None),
        "warnings": warnings,
    }


def _view_angle_deg(meta: dict, conditions: PvConditions) -> float | None:
    """Angle between the camera axis and the module normal (0 = perpendicular)."""
    gimbal = meta.get("gimbal") or {}
    pitch, yaw = gimbal.get("pitch_deg"), gimbal.get("yaw_deg")
    if not isinstance(pitch, (int, float)) or not isinstance(yaw, (int, float)):
        return None
    p, y = math.radians(pitch), math.radians(yaw)
    view = (math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p))  # N, E, Up
    tilt = math.radians(conditions.module_tilt_deg or 0.0)
    az = math.radians(conditions.module_azimuth_deg or 180.0)
    normal = (math.sin(tilt) * math.cos(az), math.sin(tilt) * math.sin(az), math.cos(tilt))
    cosine = -sum(a * b for a, b in zip(view, normal))
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


@dataclass
class _Checks:
    items: list = field(default_factory=list)

    def add(self, key, label, value, limit, status, note=""):
        self.items.append({"id": key, "label": label, "value": value, "limit": limit,
                           "status": status, "note": note})


def condition_checks(meta: dict, conditions: PvConditions, *, ground_sample_m: float | None,
                     thresholds: PvThresholds, emissivity: float | None) -> list[dict]:
    c = _Checks()
    g = conditions.irradiance_wm2
    c.add("irradiance", "Einstrahlung in Modulebene", g, "≥ 600 W/m²",
          "unknown" if g is None else "ok" if g >= 600 else "fail",
          "Ohne ausreichende Einstrahlung sind Fehlerbilder nicht sicher sichtbar.")
    w = conditions.wind_kmh
    c.add("wind", "Windgeschwindigkeit", w, "≤ 28 km/h (4 Bft)",
          "unknown" if w is None else "ok" if w <= 28 else "fail", "Wind kühlt Module ungleichmäßig.")
    o = conditions.cloud_okta
    c.add("clouds", "Bewölkung", o, "≤ 2/8",
          "unknown" if o is None else "ok" if o <= 2 else "fail", "Wolkenschatten ändern die Einstrahlung.")
    angle = _view_angle_deg(meta, conditions)
    c.add("view_angle", "Blickwinkel zur Modulnormalen",
          round(angle, 1) if angle is not None else None, "≤ 30° (Richtwert)",
          "unknown" if angle is None else "ok" if angle <= 30 else "warn",
          "Flache Blickwinkel erhöhen Reflexion und senken die gemessene Temperatur."
          + ("" if conditions.module_tilt_deg is not None else " Modulneigung nicht angegeben: horizontal angenommen."))
    px = (thresholds.cell_size_m / ground_sample_m) if ground_sample_m else None
    c.add("resolution", "Auflösung (Pixel je Zellkante)",
          round(px, 1) if px else None, "≥ 5 px/Zelle (Richtwert)",
          "unknown" if px is None else "ok" if px >= 5 else "warn",
          f"Bodenauflösung {ground_sample_m * 100:.1f} cm/px" if ground_sample_m else
          "Bodenauflösung unbekannt (Höhe/Optik fehlt).")
    c.add("emissivity", "Emissionsgrad", emissivity, "Modulglas ca. 0,85 (Richtwert)",
          "warn" if emissivity is None else "ok",
          "Wert aus der Aufnahme verwendet – für Glasoberflächen explizit setzen."
          if emissivity is None else "")
    c.add("radiometric", "Radiometrische Daten", bool(meta.get("radiometric")), "erforderlich",
          "ok" if meta.get("radiometric") else "fail", "")
    return c.items
