"""Read-only nadir camera footprint estimates for polygon flight-strip previews.

The DJI specifications publish diagonal FOV and maximum image dimensions.
For a rectangular nadir frame (landscape, no tilt, level ground), derive
cross-track/along-track footprint from the diagonal FOV and image aspect ratio.
This is an *estimate*, not a calibrated sensor model or a safe flight plan.
No camera is connected and no capture or DJI command is issued.
"""
from __future__ import annotations

from math import hypot, isfinite, radians, tan
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ProfileId = Literal[
    "matrice-4e-wide", "matrice-4t-wide",
    "mavic-3e-wide", "mavic-3t-wide",
    "mavic-3m-rgb", "mavic-3m-ms",
]

# Diagonal FoV and maximum still-image resolution, published by DJI.
# 48MP wide-angle profiles model the 48MP capture mode, not the 12MP mode.
# Values are *not* lens-calibration or focal-length certificates.
CAMERA_PROFILES: dict[str, dict] = {
    "matrice-4e-wide": {
        "label": "Matrice 4E · Weitwinkel 20 MP",
        "diagonal_fov_deg": 84.0, "image_width_px": 5280, "image_height_px": 3956,
        "mode": "20 MP",
        "source": "https://www.dji.com/support/product/matrice-4-series",
    },
    "matrice-4t-wide": {
        "label": "Matrice 4T · Weitwinkel 48 MP",
        "diagonal_fov_deg": 82.0, "image_width_px": 8064, "image_height_px": 6048,
        "mode": "48 MP (nicht 12 MP)",
        "source": "https://www.dji.com/support/product/matrice-4-series",
    },
    "mavic-3e-wide": {
        "label": "Mavic 3E · Weitwinkel 20 MP",
        "diagonal_fov_deg": 84.0, "image_width_px": 5280, "image_height_px": 3956,
        "mode": "20 MP",
        "source": "https://www.dji.com/support/product/mavic-3-enterprise",
    },
    "mavic-3t-wide": {
        "label": "Mavic 3T · Weitwinkel 48 MP",
        "diagonal_fov_deg": 84.0, "image_width_px": 8000, "image_height_px": 6000,
        "mode": "48 MP (nicht 12 MP)",
        "source": "https://www.dji.com/support/product/mavic-3-enterprise",
    },
    "mavic-3m-rgb": {
        "label": "Mavic 3M · RGB 20 MP",
        "diagonal_fov_deg": 84.0, "image_width_px": 5280, "image_height_px": 3956,
        "mode": "RGB 20 MP",
        "source": "https://enterprise.dji.com/mavic-3-m/specs",
    },
    "mavic-3m-ms": {
        "label": "Mavic 3M · Multispektral 5 MP",
        "diagonal_fov_deg": 73.91, "image_width_px": 2592, "image_height_px": 1944,
        "mode": "G/R/RE/NIR 5 MP",
        "source": "https://enterprise.dji.com/mavic-3-m/specs",
    },
}


class SurveyCameraRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_id: ProfileId
    height_agl_m: float = Field(default=60, ge=10, le=300, allow_inf_nan=False)
    side_overlap_pct: float = Field(default=70, ge=40, le=90, allow_inf_nan=False)
    front_overlap_pct: float = Field(default=80, ge=40, le=90, allow_inf_nan=False)


def camera_footprint(settings: SurveyCameraRequest) -> dict:
    """Return planning optics and suggested spacing/trigger interval in metres.

    Width is perpendicular to the flight line if images are landscape, with
    sensor width aligned across-track. No tilt, perspective, rolling-shutter,
    distortion, terrain, exposure interval, speed or airspace checks.
    """
    p = CAMERA_PROFILES[settings.profile_id]
    width_px = p["image_width_px"]
    height_px = p["image_height_px"]
    diagonal_px = hypot(width_px, height_px)
    diagonal_radius_m = settings.height_agl_m * tan(radians(p["diagonal_fov_deg"]) / 2)
    width_m = 2 * diagonal_radius_m * (width_px / diagonal_px)
    length_m = 2 * diagonal_radius_m * (height_px / diagonal_px)
    spacing = width_m * (1 - settings.side_overlap_pct / 100)
    trigger_interval = length_m * (1 - settings.front_overlap_pct / 100)
    if not all(isfinite(x) and x > 0 for x in
               (width_m, length_m, spacing, trigger_interval)):
        raise ValueError("Camera optics do not permit a finite footprint")
    return {
        "profile_id": settings.profile_id,
        "profile_label": p["label"],
        "capture_mode": p["mode"],
        "height_agl_m": settings.height_agl_m,
        "side_overlap_pct": settings.side_overlap_pct,
        "front_overlap_pct": settings.front_overlap_pct,
        "footprint_width_m": round(width_m, 2),
        "footprint_length_m": round(length_m, 2),
        "gsd_cm_px": round(100 * width_m / width_px, 3),
        "spacing_m": round(spacing, 3),
        "trigger_interval_m": round(trigger_interval, 3),
        "source": p["source"],
        "note": (
            "Approximate nadir/level-ground optics from DJI diagonal FOV and "
            "max photo dimensions. 48 MP is not 12 MP mode. No camera calibration, "
            "terrain clearance, shutter, airspace, safe turns or DJI mission export."
        ),
    }
