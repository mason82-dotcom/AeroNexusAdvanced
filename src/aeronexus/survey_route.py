"""Schematic-only survey strip connections; never flight commands or wayline export.

Straight connectors do NOT account for turn radius, obstacles, terrain or airspace.
"""
from __future__ import annotations

from math import ceil, cos, hypot, radians
from pydantic import BaseModel, ConfigDict, Field


class SurveyRouteOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    speed_mps: float = Field(default=5.0, ge=1, le=15, allow_inf_nan=False)
    turn_delay_s: float = Field(default=5.0, ge=0, le=60, allow_inf_nan=False)


def _distance_m(a: dict, b: dict) -> float:
    mean_lat = (a["latitude"] + b["latitude"]) / 2
    return hypot(
        (b["longitude"] - a["longitude"]) * 111320 * cos(radians(mean_lat)),
        (b["latitude"] - a["latitude"]) * 111132,
    )


def build_schematic_route(legs: list[list[dict]], survey_length_m: float,
                          options: SurveyRouteOptions) -> dict:
    """Join ordered strip endpoints as *unverified* straight-line sketches."""
    if not 1 <= len(legs) <= 200 or any(len(leg) != 2 for leg in legs):
        raise ValueError("Schematic route requires 1–200 two-point strips")
    points, connectors = [], []
    for i, (start, finish) in enumerate(legs):
        points.append({"index": 2 * i + 1, "role": "strip_start", **start})
        points.append({"index": 2 * i + 2, "role": "strip_end", **finish})
        if i + 1 < len(legs):
            next_start = legs[i + 1][0]
            connectors.append({
                "after_strip": i + 1,
                "start": dict(finish),
                "end": dict(next_start),
                "distance_m": round(_distance_m(finish, next_start), 2),
                "clearance_verified": False,
            })
    connecting_m = sum(c["distance_m"] for c in connectors)
    total_m = survey_length_m + connecting_m
    return {
        "kind": "schematic-route-preview",
        "mission_ready": False,
        "clearance_verified": False,
        "waypoint_count": len(points),
        "points": points,
        "connectors": connectors,
        "connector_count": len(connectors),
        "survey_distance_m": round(survey_length_m, 1),
        "connector_distance_m": round(connecting_m, 1),
        "total_distance_m": round(total_m, 1),
        "speed_mps": options.speed_mps,
        "turn_delay_s": options.turn_delay_s,
        "estimated_duration_s": ceil(total_m / options.speed_mps
                                     + len(connectors) * options.turn_delay_s),
        "warnings": [
            "Straight links are schematic, not flyable turns; they may leave the polygon.",
            "No terrain, obstacle, airspace, safety clearance or turn-radius validation.",
            "Duration omits launch, landing, RTH, wind, acceleration and battery reserves.",
            "No DJI mission upload, waypoint actions, WPML export or commands.",
        ],
    }
