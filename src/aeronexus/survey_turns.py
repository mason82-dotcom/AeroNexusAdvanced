"""Optional, non-executable circular fillets for read-only survey previews.

Constructs tangent circular arcs at the endpoints of adjacent clipped survey
strips. These are geometric approximations ONLY, not DJI flight trajectories:
no dynamics, terrain, obstacle, airspace, battery or RTH validation.
"""
from __future__ import annotations

from math import acos, atan2, ceil, cos, degrees, hypot, pi, radians, sin, tan

Vec = tuple[float, float]
EPS = 1e-8


def _add(a: Vec, b: Vec) -> Vec:
    return a[0] + b[0], a[1] + b[1]


def _sub(a: Vec, b: Vec) -> Vec:
    return a[0] - b[0], a[1] - b[1]


def _scale(v: Vec, n: float) -> Vec:
    return v[0] * n, v[1] * n


def _cross(a: Vec, b: Vec) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _norm(v: Vec) -> float:
    return hypot(*v)


def _fillet(a: Vec, b: Vec, c: Vec, radius: float) -> dict | None:
    """Return a tangent arc rounding A->B->C, or None if no finite turn."""
    before = _sub(b, a)
    after = _sub(c, b)
    first_length, second_length = _norm(before), _norm(after)
    if min(first_length, second_length) < 0.1:
        return None
    incoming = _scale(before, 1 / first_length)
    outgoing = _scale(after, 1 / second_length)
    angle = acos(max(-1., min(1., _dot(incoming, outgoing))))
    direction = _cross(incoming, outgoing)
    if angle < radians(1) or pi - angle < radians(1) or abs(direction) < 1e-7:
        return None
    trim = radius * tan(angle / 2)
    if trim >= first_length - 0.1 or trim >= second_length - 0.1:
        return None
    entry = _sub(b, _scale(incoming, trim))
    exit = _add(b, _scale(outgoing, trim))
    side = 1 if direction > 0 else -1
    normal = (-incoming[1] * side, incoming[0] * side)
    center = _add(entry, _scale(normal, radius))
    angle0 = atan2(entry[1] - center[1], entry[0] - center[0])
    # Segments <= 0.75 m and <= 4 deg provide a bounded approximate
    # 2D display and boundary check; not an exact continuous clearance proof.
    steps = max(2, ceil(radius * angle / .75), ceil(angle / radians(4)))
    positions = [(
        center[0] + radius * cos(angle0 + side * angle * i / steps),
        center[1] + radius * sin(angle0 + side * angle * i / steps),
    ) for i in range(steps + 1)]
    positions[0], positions[-1] = entry, exit
    return {"points": positions, "trim": trim, "arc_length": radius * angle,
            "angle_deg": degrees(angle)}


def _on_edge(p: Vec, a: Vec, b: Vec) -> bool:
    span = _sub(b, a)
    offset = _sub(p, a)
    length = _norm(span)
    return (length > EPS and abs(_cross(span, offset)) <= 1e-6 * length
            and -1e-6 <= _dot(offset, span) <= _dot(span, span) + 1e-6)


def _inside_or_edge(p: Vec, poly: list[Vec]) -> bool:
    inside = False
    x, y = p
    for a, b in zip(poly, poly[1:] + poly[:1]):
        if _on_edge(p, a, b):
            return True
        if (a[1] > y) != (b[1] > y):
            x_cross = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if x < x_cross:
                inside = not inside
    return inside


def _segment_in_polygon(a: Vec, b: Vec, poly: list[Vec]) -> bool:
    """Split at exact polygon-edge intersections, inspect each interval."""
    direction = _sub(b, a)
    if _norm(direction) < 1e-8:
        return _inside_or_edge(a, poly)
    cuts = [0., 1.]
    for p, q in zip(poly, poly[1:] + poly[:1]):
        edge = _sub(q, p)
        denom = _cross(direction, edge)
        if abs(denom) < EPS:
            continue
        t = _cross(_sub(p, a), edge) / denom
        u = _cross(_sub(p, a), direction) / denom
        if -1e-7 <= t <= 1 + 1e-7 and -1e-7 <= u <= 1 + 1e-7:
            cuts.append(max(0., min(1., t)))
    cuts.sort()
    return all(_inside_or_edge(_add(a, _scale(direction, (t0 + t1) / 2)), poly)
               for t0, t1 in zip(cuts, cuts[1:]) if t1 - t0 > 1e-9)


def build_turn_geometry(legs: list[list[dict]], polygon: list[dict],
                        survey_distance_m: float, radius_m: float,
                        speed_mps: float, turn_delay_s: float) -> dict:
    """Return optional geometric fillets, with explicit fail-closed flags.

    Missing/unconstructible arcs are NOT replaced with claimed valid turns.
    Even a fully constructed curve is NEVER an executable or safe flight path.
    """
    if not 1 <= len(legs) <= 200 or not 3 <= len(polygon) <= 128:
        raise ValueError("Invalid preview geometry size")
    lat0 = sum(p["latitude"] for p in polygon) / len(polygon)
    lon0 = sum(p["longitude"] for p in polygon) / len(polygon)
    sx = 111320. * cos(radians(lat0))
    sy = 111132.
    if sx < 1000.:
        raise ValueError("Local turn geometry unavailable at extreme latitudes")

    def xy(p: dict) -> Vec:
        return ((p["longitude"] - lon0) * sx,
                (p["latitude"] - lat0) * sy)

    def gps(p: Vec) -> dict:
        return {"latitude": round(lat0 + p[1] / sy, 7),
                "longitude": round(lon0 + p[0] / sx, 7)}

    poly = [xy(p) for p in polygon]
    strips = [(xy(leg[0]), xy(leg[1])) for leg in legs]
    candidates: list[dict] = []
    for i in range(len(strips) - 1):
        a, b = strips[i]
        c, d = strips[i + 1]
        first = _fillet(a, b, c, radius_m)
        second = _fillet(b, c, d, radius_m)
        available = first is not None and second is not None
        distance = _norm(_sub(c, b))
        if available and first["trim"] + second["trim"] >= distance - .1:
            available = False
        candidates.append({
            "after_strip": i + 1,
            "geometry_available": available,
            "reason": None if available else "insufficient_straight_length_or_turn_angle",
            "_first": first, "_second": second, "_distance": distance,
        })

    # Adjacent connectors consume the beginning and end of the same strip.
    # Reject both rounded connections if those cuts would overlap.
    for i, (a, b) in enumerate(strips):
        previous = candidates[i - 1] if i > 0 else None
        following = candidates[i] if i < len(candidates) else None
        begin = (previous["_second"]["trim"] if previous and previous["geometry_available"]
                 else 0.)
        end = (following["_first"]["trim"] if following and following["geometry_available"]
               else 0.)
        if begin + end >= _norm(_sub(b, a)) - .1:
            for item in (previous, following):
                if item and item["geometry_available"]:
                    item["geometry_available"] = False
                    item["reason"] = "adjacent_fillets_overlap"

    links = []
    delta_m = 0.
    exits = 0
    for item in candidates:
        if not item["geometry_available"]:
            links.append({
                "after_strip": item["after_strip"],
                "geometry_available": False,
                "reason": item["reason"],
                "polygon_exit_detected": None,
                "curve_points": [],
            })
            continue
        first, second = item["_first"], item["_second"]
        points = first["points"] + second["points"]
        # Between the two arcs the section from first.exit to second.entry
        # is a straight line. Both ends are included in points already.
        exits_poly = any(
            not _segment_in_polygon(a, b, poly)
            for a, b in zip(points, points[1:])
        )
        if exits_poly:
            exits += 1
        curve_length = (first["arc_length"] + second["arc_length"]
                        + item["_distance"] - first["trim"] - second["trim"])
        # Replace two corners: cut trim from *both* incident straights.
        delta_m += (first["arc_length"] + second["arc_length"]
                    - 2 * (first["trim"] + second["trim"]))
        links.append({
            "after_strip": item["after_strip"],
            "geometry_available": True,
            "reason": None,
            "polygon_exit_detected": exits_poly,
            "curve_points": [gps(p) for p in points],
            "curve_distance_m": round(curve_length, 2),
            "entry_turn_deg": round(first["angle_deg"], 2),
            "exit_turn_deg": round(second["angle_deg"], 2),
        })

    completed = all(link["geometry_available"] for link in links)
    base = survey_distance_m + sum(item["_distance"] for item in candidates)
    curved = base + delta_m if completed else None
    return {
        "kind": "geometric-turn-analysis",
        "radius_m": radius_m,
        "radius_model": "tangent_circular_fillets_2d",
        "geometry_complete": completed,
        "geometry_available_count": sum(link["geometry_available"] for link in links),
        "geometry_rejected_count": len(links) - sum(link["geometry_available"] for link in links),
        "polygon_exit_count": exits,
        "polygon_check": "polygon_edge_intersections_on_sampled_arc_chords_only",
        "curve_total_distance_m": round(curved, 1) if curved is not None else None,
        "estimated_duration_s": (ceil(curved / speed_mps + len(links) * turn_delay_s)
                                 if curved is not None else None),
        "connections": links,
        "ready_for_flight": False,
        "terrain_verified": False,
        "obstacles_verified": False,
        "battery_verified": False,
        "rth_verified": False,
        "warnings": [
            "Circular fillets approximate 2D geometry only; no multirotor dynamics or turn feasibility.",
            "Polygon crossings are detected on sampled arc chords, not a flight clearance proof.",
            "No terrain elevation, obstacles, airspace, wind, RTH or battery reserve checks.",
            "Estimated time excludes takeoff, landing, climbs and acceleration.",
            "Never use this data for DJI mission execution or export.",
        ],
    }
