"""Local geo-object validation and preview-only parallel survey lines.

No DJI API calls, flight execution, WPML generation or airspace clearance.
All calculations use a small local tangent-plane approximation. Reject
geometries where that approximation could be misleading.
"""
from __future__ import annotations

from math import ceil, cos, radians, sin
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .survey_camera import SurveyCameraRequest, camera_footprint
from .survey_route import SurveyRouteOptions, build_schematic_route


class GeoPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)


class GeoObject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["point", "line", "polygon", "circle"]
    vertices: list[GeoPoint] = Field(min_length=1, max_length=128)
    radius_m: float | None = Field(default=None, gt=0, le=5000, allow_inf_nan=False)

    @model_validator(mode="after")
    def valid_geometry(self):
        count = len(self.vertices)
        requirements = {"point": (1, 1), "line": (2, 128),
                        "polygon": (3, 128), "circle": (1, 1)}
        minimum, maximum = requirements[self.kind]
        if not minimum <= count <= maximum:
            raise ValueError("Invalid vertex count for geometry kind")
        if (self.kind == "circle") != (self.radius_m is not None):
            raise ValueError("Radius is allowed only for circles and required there")
        if self.kind in ("line", "polygon"):
            # Single local planning area: no dateline wrap or massive extents.
            latitudes = [p.latitude for p in self.vertices]
            longitudes = [p.longitude for p in self.vertices]
            if max(latitudes) - min(latitudes) > .45 or max(longitudes) - min(longitudes) > .45:
                raise ValueError("Geometry spans too large an area or crosses the dateline")
            if any(a.latitude == b.latitude and a.longitude == b.longitude
                   for a, b in zip(self.vertices, self.vertices[1:])):
                raise ValueError("Adjacent vertices must be different")
        if self.kind == "polygon":
            if len({(p.latitude, p.longitude) for p in self.vertices}) != count:
                raise ValueError("Polygon vertices must be distinct; do not repeat first vertex")
            if abs(_polygon_area([(p.longitude, p.latitude) for p in self.vertices])) < 1e-12:
                raise ValueError("Polygon has zero area")
            if _self_intersects([(p.longitude, p.latitude) for p in self.vertices]):
                raise ValueError("Self-intersecting polygons are not supported")
        return self


class SurveyPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    polygon: GeoObject
    spacing_m: float = Field(default=20, ge=2, le=200, allow_inf_nan=False)
    bearing_deg: float = Field(default=0, ge=0, lt=360, allow_inf_nan=False)
    camera: SurveyCameraRequest | None = None
    route: SurveyRouteOptions | None = None

    @model_validator(mode="after")
    def require_polygon(self):
        if self.polygon.kind != "polygon":
            raise ValueError("Survey lines require a polygon")
        return self


def _polygon_area(poly: list[tuple[float, float]]) -> float:
    return .5 * sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2)
                    in zip(poly, poly[1:] + poly[:1]))


def _self_intersects(poly: list[tuple[float, float]]) -> bool:
    def orientation(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def on_segment(a, b, c):
        return min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= c[1] <= max(a[1], b[1])
    def intersects(a, b, c, d):
        o1, o2, o3, o4 = (orientation(a,b,c), orientation(a,b,d),
                           orientation(c,d,a), orientation(c,d,b))
        if o1*o2 < 0 and o3*o4 < 0:
            return True
        return ((o1 == 0 and on_segment(a,b,c)) or (o2 == 0 and on_segment(a,b,d))
                or (o3 == 0 and on_segment(c,d,a)) or (o4 == 0 and on_segment(c,d,b)))
    n = len(poly)
    for i in range(n):
        for j in range(i+1, n):
            if j in (i, i+1) or (i == 0 and j == n-1):
                continue
            if intersects(poly[i],poly[(i+1)%n],poly[j],poly[(j+1)%n]):
                return True
    return False


def generate_survey_preview(request: SurveyPlanRequest) -> dict:
    """Return isolated parallel legs clipped to polygon; no flight route.

    Flight turns, obstacle clearance, battery, elevation and RTH are unknown.
    """
    optics = camera_footprint(request.camera) if request.camera else None
    spacing_m = optics["spacing_m"] if optics else request.spacing_m
    if not 2 <= spacing_m <= 200:
        raise ValueError("Camera-derived spacing outside 2–200 m; adjust height/overlap")
    photo_estimate = 0
    vertices = request.polygon.vertices
    lat0 = sum(p.latitude for p in vertices) / len(vertices)
    lon0 = sum(p.longitude for p in vertices) / len(vertices)
    scale_x = 111320.0 * cos(radians(lat0))
    scale_y = 111132.0
    if scale_x < 1000:
        raise ValueError("Survey planning unavailable at extreme latitudes")
    heading = radians(request.bearing_deg)
    along = (sin(heading), cos(heading))
    normal = (cos(heading), -sin(heading))
    xy = [((p.longitude-lon0)*scale_x, (p.latitude-lat0)*scale_y) for p in vertices]
    uv = [(x*normal[0]+y*normal[1], x*along[0]+y*along[1]) for x,y in xy]
    left, right = min(u for u,_ in uv), max(u for u,_ in uv)
    if right-left < .1:
        raise ValueError("Survey area too narrow")
    span = right-left
    nlines = max(1, int(span/spacing_m) + 1)
    if nlines > 150:
        raise ValueError("Too many flight lines; increase spacing")
    offsets = [(left+right)/2] if nlines==1 else [
        left + span*(i+.5)/nlines for i in range(nlines)]
    legs = []
    total = 0.0
    for u in offsets:
        crossings = []
        for (a,b),(c,d) in zip(uv,uv[1:]+uv[:1]):
            if (a<=u<c) or (c<=u<a):
                crossings.append(b+(u-a)*(d-b)/(c-a))
        crossings.sort()
        if len(crossings)%2:
            raise ValueError("Polygon clipping failed")
        for j in range(0,len(crossings),2):
            v1,v2=crossings[j:j+2]
            if v2-v1 < .1:
                continue
            if len(legs)>=200:
                raise ValueError("Too many clipped legs")
            def to_gps(v):
                x=u*normal[0]+v*along[0]
                y=u*normal[1]+v*along[1]
                return {"latitude":round(lat0+y/scale_y,7),
                        "longitude":round(lon0+x/scale_x,7)}
            segment = [to_gps(v1),to_gps(v2)]
            if len(legs)%2:
                segment.reverse()
            legs.append(segment)
            total += v2-v1
            if optics:
                photo_estimate += ceil((v2-v1)/optics["trigger_interval_m"])+1
    if not legs:
        raise ValueError("No survey lines inside polygon")
    result = {"kind":"survey-preview","legs":legs,"leg_count":len(legs),
              "distance_m":round(total,1),
              "note":"Preview only: independent legs, no safe connecting turns, terrain, obstacles or DJI mission export."}
    if optics:
        result["camera_plan"] = {**optics, "estimated_photo_count": photo_estimate}
    if request.route is not None:
        result["route_preview"] = build_schematic_route(legs, total, request.route)
    return result
