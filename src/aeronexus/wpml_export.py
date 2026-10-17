"""Conservative offline DJI WPML waypoint KMZ exporter.

Reference: DJI Cloud API WPML template.kml, waylines.wpml, product support.
Only named Mavic 3 Enterprise / Matrice 4 waypoint profiles; no flight API.
Heights are uniform, relative to actual takeoff point. Per-waypoint ellipsoid
heights require surveyed elevation data and are intentionally not guessed.
"""
from io import BytesIO
from math import isfinite
from zipfile import ZIP_DEFLATED, ZipFile, BadZipFile
import xml.etree.ElementTree as ET

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Literal


KML_NS = "http://www.opengis.net/kml/2.2"
WPML_NS = "http://www.dji.com/wpmz/1.0.2"
ET.register_namespace("", KML_NS)
ET.register_namespace("wpml", WPML_NS)

# Official DJI product support enums (aircraft domain 0, camera domain 1).
MODELS = {
    "matrice4t": (99, 1, 89, 0),
    "matrice4e": (99, 0, 88, 0),
    "mavic3e": (77, 0, 66, 0),
    "mavic3t": (77, 1, 67, 0),
    "mavic3m": (77, 2, 68, 0),
    "mavic3ta": (77, 3, 129, 0),
}
MODEL_LABELS = {
    "matrice4t": "Matrice 4T", "matrice4e": "Matrice 4E",
    "mavic3e": "Mavic 3E", "mavic3t": "Mavic 3T",
    "mavic3m": "Mavic 3M", "mavic3ta": "Mavic 3TA",
}
MissionModel = Literal["matrice4t", "matrice4e", "mavic3e", "mavic3t", "mavic3m", "mavic3ta"]


def _k(tag: str) -> str:
    return f"{{{KML_NS}}}{tag}"


def _w(tag: str) -> str:
    return f"{{{WPML_NS}}}{tag}"


def _set(parent: ET.Element, tag: str, value) -> ET.Element:
    item = ET.SubElement(parent, _w(tag))
    item.text = str(value)
    return item


def _num(value: float) -> str:
    return format(value, ".7f").rstrip("0").rstrip(".") if value else "0"


class Waypoint(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    take_photo: bool = False

    @model_validator(mode="after")
    def valid_gps_fix(self) -> "Waypoint":
        # DJI uses 0/0 as a missing-fix sentinel, not a usable wayline point.
        if self.latitude == 0 and self.longitude == 0:
            raise ValueError("Waypoint at 0,0 is not a valid GPS fix")
        return self

    @field_validator("latitude", "longitude")
    @classmethod
    def finite(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("Coordinate must be finite")
        return value


class WaypointMission(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    drone_model: MissionModel = "matrice4t"
    altitude_m: float = Field(default=50.0, ge=2.0, le=500)
    speed_mps: float = Field(default=5.0, gt=0, le=15)
    takeoff_security_height_m: float = Field(default=20.0, ge=1.2, le=1500)
    rth_height_m: float = Field(default=60.0, ge=2, le=500)
    finish_action: Literal["goHome", "noAction"] = "goHome"
    close_route: bool = False  # extra real return-to-first waypoint in exported WPML
    waypoints: list[Waypoint] = Field(default_factory=list, max_length=500)

    @field_validator("altitude_m", "speed_mps", "takeoff_security_height_m", "rth_height_m")
    @classmethod
    def finite(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("Altitude and speed must be finite")
        return value

    @field_validator("name")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Mission name is required")
        return value.strip()


def waypoints_for_export(mission: WaypointMission) -> list[Waypoint]:
    """Resolved flight route, not just a drawn polygon.

    A closed route ends with a genuine executable WPML waypoint at the first
    waypoint's location. Never automatically repeat the first photo action.
    Keep user waypoints separate so turning the option off is reversible.
    """
    points = list(mission.waypoints)
    if mission.close_route and len(points) >= 2:
        first, last = points[0], points[-1]
        if (first.latitude, first.longitude) != (last.latitude, last.longitude):
            points.append(Waypoint(latitude=first.latitude,
                                   longitude=first.longitude, take_photo=False))
    return points


def _mission_config(doc: ET.Element, mission: WaypointMission) -> None:
    config = ET.SubElement(doc, _w("missionConfig"))
    for key, value in (
        ("flyToWaylineMode", "safely"),
        ("finishAction", mission.finish_action),
        ("exitOnRCLost", "executeLostAction"),
        ("executeRCLostAction", "goBack"),
        ("takeOffSecurityHeight", _num(mission.takeoff_security_height_m)),
        ("globalTransitionalSpeed", _num(mission.speed_mps)),
        ("globalRTHHeight", _num(mission.rth_height_m)),
    ):
        _set(config, key, value)
    drone_enum, drone_sub, camera_enum, camera_sub = MODELS[mission.drone_model]
    drone = ET.SubElement(config, _w("droneInfo"))
    _set(drone, "droneEnumValue", drone_enum)
    _set(drone, "droneSubEnumValue", drone_sub)
    payload = ET.SubElement(config, _w("payloadInfo"))
    _set(payload, "payloadEnumValue", camera_enum)
    _set(payload, "payloadSubEnumValue", camera_sub)
    _set(payload, "payloadPositionIndex", 0)


def _photo_action(place: ET.Element, index: int) -> None:
    group = ET.SubElement(place, _w("actionGroup"))
    for key, value in (
        ("actionGroupId", index),
        ("actionGroupStartIndex", index),
        ("actionGroupEndIndex", index),
        ("actionGroupMode", "sequence"),
    ):
        _set(group, key, value)
    trigger = ET.SubElement(group, _w("actionTrigger"))
    _set(trigger, "actionTriggerType", "reachPoint")
    action = ET.SubElement(group, _w("action"))
    _set(action, "actionId", 0)
    _set(action, "actionActuatorFunc", "takePhoto")
    params = ET.SubElement(action, _w("actionActuatorFuncParam"))
    _set(params, "fileSuffix", f"p{index:03d}")
    _set(params, "payloadPositionIndex", 0)


def _xml(mission: WaypointMission, *, template: bool, timestamp_ms: int) -> bytes:
    root = ET.Element(_k("kml"))
    doc = ET.SubElement(root, _k("Document"))
    ET.SubElement(doc, _k("name")).text = mission.name
    ET.SubElement(doc, _k("description")).text = mission.description
    if template:
        _set(doc, "author", "AeroNexusAdvanced")
        _set(doc, "createTime", timestamp_ms)
        _set(doc, "updateTime", timestamp_ms)
    _mission_config(doc, mission)
    folder = ET.SubElement(doc, _k("Folder"))
    if template:
        _set(folder, "templateType", "waypoint")
        _set(folder, "templateId", 0)
        coords = ET.SubElement(folder, _w("waylineCoordinateSysParam"))
        _set(coords, "coordinateMode", "WGS84")
        _set(coords, "heightMode", "relativeToStartPoint")
        _set(coords, "positioningType", "GPS")
        _set(folder, "autoFlightSpeed", _num(mission.speed_mps))
        _set(folder, "globalHeight", _num(mission.altitude_m))
        _set(folder, "gimbalPitchMode", "usePointSetting")
        heading = ET.SubElement(folder, _w("globalWaypointHeadingParam"))
        _set(heading, "waypointHeadingMode", "followWayline")
        _set(folder, "globalWaypointTurnMode", "toPointAndStopWithDiscontinuityCurvature")
        _set(folder, "globalUseStraightLine", 1)
    else:
        _set(folder, "templateId", 0)
        _set(folder, "executeHeightMode", "relativeToStartPoint")
        _set(folder, "waylineId", 0)
        _set(folder, "autoFlightSpeed", _num(mission.speed_mps))
    for index, wp in enumerate(waypoints_for_export(mission)):
        place = ET.SubElement(folder, _k("Placemark"))
        point = ET.SubElement(place, _k("Point"))
        ET.SubElement(point, _k("coordinates")).text = (
            f"{_num(wp.longitude)},{_num(wp.latitude)}")
        _set(place, "index", index)
        if template:
            _set(place, "useGlobalHeight", 1)
            _set(place, "useGlobalSpeed", 1)
            _set(place, "useGlobalHeadingParam", 1)
            _set(place, "useGlobalTurnParam", 1)
            _set(place, "gimbalPitchAngle", 0)
        else:
            _set(place, "executeHeight", _num(mission.altitude_m))
            _set(place, "waypointSpeed", _num(mission.speed_mps))
            heading = ET.SubElement(place, _w("waypointHeadingParam"))
            _set(heading, "waypointHeadingMode", "followWayline")
            turning = ET.SubElement(place, _w("waypointTurnParam"))
            _set(turning, "waypointTurnMode", "toPointAndStopWithDiscontinuityCurvature")
            _set(turning, "waypointTurnDampingDist", 0)
        if wp.take_photo:
            _photo_action(place, index)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def export_kmz(mission: WaypointMission, *, timestamp_ms: int) -> bytes:
    """Offline download only; generated route is NEVER sent to a device.

    This is an interoperable WPML waypoint subset, not a DJI flight-safety
    validation or guaranteed firmware compatibility certification.
    """
    resolved = waypoints_for_export(mission)
    if not 2 <= len(resolved) <= 500:
        raise ValueError("WPML export requires between 2 and 500 executed waypoints")
    if mission.close_route:
        # Closing a route is meaningful only with at least 3 distinct points.
        coordinates = {(point.latitude, point.longitude) for point in mission.waypoints}
        if len(coordinates) < 3:
            raise ValueError("Closing a route requires at least 3 distinct waypoints")
    if timestamp_ms < 0:
        raise ValueError("Invalid timestamp")
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("wpmz/template.kml", _xml(mission, template=True, timestamp_ms=timestamp_ms))
        archive.writestr("wpmz/waylines.wpml", _xml(mission, template=False, timestamp_ms=timestamp_ms))
    return buffer.getvalue()


def import_kmz(data: bytes) -> WaypointMission:
    """Import our own supported waypoint subset, never arbitrary DJI actions.

    Refuse anything not generated by AeroNexusAdvanced: generic DJI Pilot 2
    routes can contain complex actions and height references that would be
    dangerously lost if silently rewritten.
    """
    if not data or len(data) > 2 * 1024 * 1024:
        raise ValueError("Import limited to 2 MiB AeroNexus waypoint KMZ files")
    names = {"wpmz/template.kml", "wpmz/waylines.wpml"}
    try:
        with ZipFile(BytesIO(data)) as archive:
            infos = archive.infolist()
            if {info.filename for info in infos} != names or len(infos) != 2:
                raise ValueError("KMZ must contain only the two AeroNexus WPML files")
            if any(info.flag_bits & 1 or (info.external_attr >> 16) & 0o170000 == 0o120000
                   or info.file_size > 1024 * 1024 for info in infos):
                raise ValueError("Encrypted, linked or oversized KMZ member rejected")
            template = ET.fromstring(archive.read("wpmz/template.kml"))
            route = ET.fromstring(archive.read("wpmz/waylines.wpml"))
    except (BadZipFile, ET.ParseError, RuntimeError, OSError) as exc:
        raise ValueError("Invalid WPML archive") from exc

    def txt(root: ET.Element, path: str) -> str:
        item = root.find(path)
        if item is None or item.text is None:
            raise ValueError("Required WPML element is missing")
        return item.text.strip()

    for root in (template, route):
        if root.tag != _k("kml"):
            raise ValueError("Unsupported KML namespace")
    if txt(template, ".//" + _w("author")) != "AeroNexusAdvanced":
        raise ValueError("Only AeroNexus-created waypoint KMZ files can be edited")
    if txt(template, ".//" + _w("templateType")) != "waypoint":
        raise ValueError("Unsupported mission type")
    if txt(template, ".//" + _w("heightMode")) != "relativeToStartPoint":
        raise ValueError("Unsupported height reference")
    if txt(route, ".//" + _w("executeHeightMode")) != "relativeToStartPoint":
        raise ValueError("Unsupported executable height reference")
    if txt(template, ".//" + _w("templateId")) != "0" or txt(route, ".//" + _w("templateId")) != "0":
        raise ValueError("Unsupported template identifier")
    if txt(route, ".//" + _w("waylineId")) != "0":
        raise ValueError("Only a single waypoint wayline is supported")
    model = None
    for name, (aircraft, subtype, camera, camera_sub) in MODELS.items():
        if (txt(route, ".//" + _w("droneEnumValue")) == str(aircraft)
                and txt(route, ".//" + _w("droneSubEnumValue")) == str(subtype)
                and txt(route, ".//" + _w("payloadEnumValue")) == str(camera)
                and txt(route, ".//" + _w("payloadSubEnumValue")) == str(camera_sub)):
            model = name
    if model is None:
        raise ValueError("Unsupported aircraft or payload model")
    route_points = route.findall(".//" + _k("Placemark"))
    template_points = template.findall(".//" + _k("Placemark"))
    if len(route_points) != len(template_points) or not 2 <= len(route_points) <= 500:
        raise ValueError("Invalid waypoint count")
    altitude = float(txt(template, ".//" + _w("globalHeight")))
    speed = float(txt(route, ".//" + _w("autoFlightSpeed")))
    waypoints = []
    for index, (point, plan) in enumerate(zip(route_points, template_points)):
        if txt(point, _w("index")) != str(index) or txt(plan, _w("index")) != str(index):
            raise ValueError("Nonsequential waypoint numbering")
        raw = txt(point, ".//" + _k("coordinates"))
        if raw != txt(plan, ".//" + _k("coordinates")):
            raise ValueError("Template and executable route disagree")
        if txt(point, _w("executeHeight")) != _num(altitude):
            raise ValueError("Per-point altitude is outside the supported subset")
        if txt(plan, _w("useGlobalHeight")) != "1":
            raise ValueError("Per-point height references are not supported")
        actions = point.findall(".//" + _w("actionActuatorFunc"))
        template_actions = plan.findall(".//" + _w("actionActuatorFunc"))
        if (len(actions) > 1 or len(template_actions) != len(actions)
                or any(a.text != "takePhoto" for a in actions + template_actions)):
            raise ValueError("Unsupported waypoint action")
        try:
            lon, lat = (float(coord) for coord in raw.split(","))
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid WGS84 waypoint") from exc
        waypoints.append({"latitude": lat, "longitude": lon,
                          "take_photo": bool(actions)})
    # AeroNexus exports "close route" as the actual final flight waypoint.
    # Recover the option from that final duplicate only when no camera action
    # would be discarded. Older explicitly repeated finish points may be
    # normalized to the same flight path with a separate reversible switch.
    closed = (
        len(waypoints) >= 4
        and (waypoints[-1]["latitude"], waypoints[-1]["longitude"])
            == (waypoints[0]["latitude"], waypoints[0]["longitude"])
        and not waypoints[-1]["take_photo"]
        and len({(point["latitude"], point["longitude"]) for point in waypoints[:-1]}) >= 3
    )
    if closed:
        waypoints.pop()
    doc = template.find(_k("Document"))
    name = doc.findtext(_k("name")) if doc is not None else None
    description = doc.findtext(_k("description")) if doc is not None else None
    mission = WaypointMission.model_validate({
        "name": name or "Importierte AeroNexus-Mission",
        "description": description or "",
        "drone_model": model,
        "altitude_m": altitude,
        "speed_mps": speed,
        "takeoff_security_height_m": float(txt(route, ".//" + _w("takeOffSecurityHeight"))),
        "rth_height_m": float(txt(route, ".//" + _w("globalRTHHeight"))),
        "finish_action": txt(route, ".//" + _w("finishAction")),
        "close_route": closed,
        "waypoints": waypoints,
    })
    # A supported file must be representable without silently dropping flight
    # semantics. Compare the ENTIRE parsed documents with our own supported
    # representation, including settings, duplicate elements and action params.
    # XML indentation/prefix spelling and the two creation timestamps are not
    # flight semantics. No generic third-party KMZ compatibility is implied.
    for actual, is_template in ((template, True), (route, False)):
        expected = ET.fromstring(_xml(mission, template=is_template, timestamp_ms=0))
        if is_template:
            for tag in ("createTime", "updateTime"):
                elements = actual.findall(_k("Document") + "/" + _w(tag))
                value = (elements[0].text or "").strip() if len(elements) == 1 else ""
                if not value.isascii() or not value.isdigit():
                    raise ValueError("Invalid AeroNexus timestamp")
                elements[0].text = "0"
        if _document_signature(actual) != _document_signature(expected):
            raise ValueError("WPML settings disagree or cannot be preserved by the supported mission format")
    return mission


def _document_signature(root: ET.Element) -> tuple:
    """Compare expanded XML names, attributes and ordered text/children.

    Only inter-element whitespace is ignored. Significant description/name
    whitespace, unknown attributes and mixed text must not disappear on import.
    Use an iterative traversal so a deeply nested invalid document cannot cause
    a recursion error in the request handler.
    """
    result = []
    stack = [(root, 0)]
    while stack:
        node, depth = stack.pop()
        text = node.text or ""
        result.append((depth, node.tag, tuple(sorted(node.attrib.items())),
                       text if text.strip() else "", (node.tail or "").strip()))
        stack.extend((child, depth + 1) for child in reversed(node))
    return tuple(result)
