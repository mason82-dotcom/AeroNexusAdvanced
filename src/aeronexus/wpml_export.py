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

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator, model_serializer
from typing import Annotated, Literal, Union


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
# Narrow, opt-in planning subset. Other DJI modes remain deliberately disabled.
HeadingMode = Literal["followWayline", "smoothTransition"]
HeadingPathMode = Literal["clockwise", "counterClockwise", "followBadArc"]
TurnMode = Literal[
    "toPointAndStopWithDiscontinuityCurvature",
    "toPointAndStopWithContinuityCurvature",
]


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


# DJI WPML Common Elements, current product matrix (2026). M3TA is listed
# as an aircraft/payload, but is NOT explicitly listed in these action rows.
# Never infer firmware compatibility from the parent M3 Enterprise family.
ACTION_MATRIX_SOURCE = (
    "https://developer.dji.com/doc/cloud-api-tutorial/en/"
    "api-reference/dji-wpml/common-element.html"
)
ACTION_MODEL_MATRIX = {
    "matrice4t": frozenset({"startRecord", "stopRecord", "focus", "zoom",
                           "gimbalRotate", "gimbalEvenlyRotate"}),
    "matrice4e": frozenset({"startRecord", "stopRecord", "focus", "zoom",
                           "gimbalRotate", "gimbalEvenlyRotate"}),
    "mavic3e": frozenset({"startRecord", "stopRecord", "focus", "zoom",
                         "gimbalRotate", "gimbalEvenlyRotate"}),
    "mavic3t": frozenset({"startRecord", "stopRecord", "focus", "zoom",
                         "gimbalRotate", "gimbalEvenlyRotate"}),
    "mavic3m": frozenset({"startRecord", "stopRecord", "focus", "zoom",
                         "gimbalRotate", "gimbalEvenlyRotate"}),
    "mavic3ta": frozenset(),  # not explicitly in the WPML action table
}
MAX_WAYPOINT_ACTIONS = 8
# Intentionally conservative gimbal pitch envelope; NOT a model calibration.
PITCH_MIN_DEG, PITCH_MAX_DEG = -90.0, 0.0

# The current DJI developer WPML reference (which includes M4E/M4T) requires
# explicit lens selection for M4 photo and start-record actions. For supported
# Mavic 3 variants it requires the global-selection flag but does not specify
# payloadLensIndex. M3TA is not listed in these action rows.
_LENS_SELECTION_MODELS = frozenset({
    "matrice4e", "matrice4t", "mavic3e", "mavic3t", "mavic3m",
})
_EXPLICIT_WIDE_LENS_MODELS = frozenset({"matrice4e", "matrice4t"})


def _camera_lens_selection(params: ET.Element, model: str, *,
                           legacy_camera_params: bool = False) -> None:
    """Emit the documented lens-selection subset, never infer thermal capture.

    Legacy mode reproduces the previously exported XML *only for strict import
    compatibility*. It must not be used for new KMZ exports.
    """
    if legacy_camera_params or model not in _LENS_SELECTION_MODELS:
        return
    if model in _EXPLICIT_WIDE_LENS_MODELS:
        _set(params, "payloadLensIndex", "wide")
    _set(params, "useGlobalPayloadLensIndex", 0)


class _CameraAction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class StartRecord(_CameraAction):
    type: Literal["startRecord"]


class StopRecord(_CameraAction):
    type: Literal["stopRecord"]


class FocusAction(_CameraAction):
    type: Literal["focus"]
    focus_x: float = Field(ge=0, le=1)
    focus_y: float = Field(ge=0, le=1)

    @field_validator("focus_x", "focus_y")
    @classmethod
    def finite_xy(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("Focus coordinate must be finite")
        return value


class ZoomAction(_CameraAction):
    type: Literal["zoom"]
    focal_length_mm: float = Field(gt=0, le=500)

    @field_validator("focal_length_mm")
    @classmethod
    def finite_length(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("Focal length must be finite")
        return value


class GimbalRotateAction(_CameraAction):
    type: Literal["gimbalRotate"]
    pitch_deg: float = Field(ge=PITCH_MIN_DEG, le=PITCH_MAX_DEG)

    @field_validator("pitch_deg")
    @classmethod
    def finite_pitch(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("Pitch must be finite")
        return value


class GimbalEvenlyRotateAction(_CameraAction):
    type: Literal["gimbalEvenlyRotate"]
    pitch_deg: float = Field(ge=PITCH_MIN_DEG, le=PITCH_MAX_DEG)

    @field_validator("pitch_deg")
    @classmethod
    def finite_pitch(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("Pitch must be finite")
        return value


WaypointAction = Annotated[
    Union[StartRecord, StopRecord, FocusAction, ZoomAction,
          GimbalRotateAction, GimbalEvenlyRotateAction],
    Field(discriminator="type"),
]


class Waypoint(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    take_photo: bool = False
    heading_angle_deg: float | None = Field(default=None, ge=-180, le=180)
    actions: list[WaypointAction] = Field(default_factory=list, max_length=MAX_WAYPOINT_ACTIONS)

    @model_serializer(mode="wrap")
    def dump_without_empty_actions(self, handler):
        data = handler(self)
        if not self.actions:
            data.pop("actions", None)
        return data

    @model_validator(mode="after")
    def valid_gps_fix(self) -> "Waypoint":
        # DJI uses 0/0 as a missing-fix sentinel, not a usable wayline point.
        if self.latitude == 0 and self.longitude == 0:
            raise ValueError("Waypoint at 0,0 is not a valid GPS fix")
        return self

    @field_validator("heading_angle_deg")
    @classmethod
    def finite_heading_angle(cls, value: float | None) -> float | None:
        if value is not None and not isfinite(value):
            raise ValueError("Heading angle must be finite")
        return value

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
    heading_mode: HeadingMode = "followWayline"
    heading_path_mode: HeadingPathMode | None = None
    turn_mode: TurnMode = "toPointAndStopWithDiscontinuityCurvature"
    close_route: bool = False  # extra real return-to-first waypoint in exported WPML
    waypoints: list[Waypoint] = Field(default_factory=list, max_length=500)

    @field_validator("altitude_m", "speed_mps", "takeoff_security_height_m", "rth_height_m")
    @classmethod
    def finite(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("Altitude and speed must be finite")
        return value

    @model_validator(mode="after")
    def validate_action_matrix(self) -> "WaypointMission":
        # Only offline export preparation. Hardware/firmware support remains
        # separately unverified; never send these actions to any aircraft.
        resolved = waypoints_for_export(self)
        if self.heading_mode == "smoothTransition":
            # No implicit closing yaw: it changes actual flight semantics.
            if self.close_route:
                raise ValueError("Smooth heading with closed route is not verified")
            if self.heading_path_mode is None:
                raise ValueError("Smooth heading requires an explicit rotation path")
            if any(point.heading_angle_deg is None for point in resolved):
                raise ValueError("Smooth heading requires an angle at every waypoint")
        elif self.heading_path_mode is not None or any(
            point.heading_angle_deg is not None for point in resolved
        ):
            raise ValueError("Heading angles/path only supported for smoothTransition")
        for index, point in enumerate(resolved):
            for action in point.actions:
                if action.type not in ACTION_MODEL_MATRIX[self.drone_model]:
                    raise ValueError("DJI WPML action not evidenced for selected aircraft model")
                if action.type == "gimbalEvenlyRotate" and index == len(resolved) - 1:
                    raise ValueError("Even gimbal rotation needs a following waypoint")
        return self

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


def _photo_action(place: ET.Element, index: int, model: str, *,
                  legacy_camera_params: bool = False) -> None:
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
    _camera_lens_selection(params, model, legacy_camera_params=legacy_camera_params)


def _extra_action(place: ET.Element, index: int, seq: int, action: WaypointAction,
                  model: str, *, legacy_camera_params: bool = False) -> None:
    """Canonical DJI WPML action groups; only the reviewed offline subset."""
    group = ET.SubElement(place, _w("actionGroup"))
    between = action.type == "gimbalEvenlyRotate"
    for key, value in (
        ("actionGroupId", 10000 + 10 * index + seq),
        ("actionGroupStartIndex", index),
        ("actionGroupEndIndex", index + 1 if between else index),
        ("actionGroupMode", "sequence"),
    ):
        _set(group, key, value)
    trigger = ET.SubElement(group, _w("actionTrigger"))
    _set(trigger, "actionTriggerType",
         "betweenAdjacentPoints" if between else "reachPoint")
    item = ET.SubElement(group, _w("action"))
    _set(item, "actionId", 0)
    _set(item, "actionActuatorFunc", action.type)
    param = ET.SubElement(item, _w("actionActuatorFuncParam"))
    if action.type == "gimbalEvenlyRotate":
        _set(param, "gimbalPitchRotateAngle", _num(action.pitch_deg))
        _set(param, "payloadPositionIndex", 0)
    else:
        _set(param, "payloadPositionIndex", 0)
        if action.type == "startRecord":
            _set(param, "fileSuffix", f"v{index:03d}")
            _camera_lens_selection(param, model, legacy_camera_params=legacy_camera_params)
        elif action.type == "focus":
            _set(param, "isPointFocus", 1)
            _set(param, "focusX", _num(action.focus_x))
            _set(param, "focusY", _num(action.focus_y))
            _set(param, "isInfiniteFocus", 0)
        elif action.type == "zoom":
            _set(param, "focalLength", _num(action.focal_length_mm))
        elif action.type == "gimbalRotate":
            for key, value in (
                ("gimbalHeadingYawBase", "north"),
                ("gimbalRotateMode", "absoluteAngle"),
                ("gimbalPitchRotateEnable", 1),
                ("gimbalPitchRotateAngle", _num(action.pitch_deg)),
                ("gimbalRollRotateEnable", 0),
                ("gimbalRollRotateAngle", 0),
                ("gimbalYawRotateEnable", 0),
                ("gimbalYawRotateAngle", 0),
                ("gimbalRotateTimeEnable", 0),
                ("gimbalRotateTime", 0),
            ):
                _set(param, key, value)


def _xml(mission: WaypointMission, *, template: bool, timestamp_ms: int,
         legacy_camera_params: bool = False) -> bytes:
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
        _set(folder, "globalWaypointTurnMode", mission.turn_mode)
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
            _set(place, "useGlobalHeadingParam",
                 0 if mission.heading_mode == "smoothTransition" else 1)
            if mission.heading_mode == "smoothTransition":
                # Template per-point override matches executable per-point yaw.
                heading = ET.SubElement(place, _w("waypointHeadingParam"))
                _set(heading, "waypointHeadingMode", "smoothTransition")
                _set(heading, "waypointHeadingAngle", _num(wp.heading_angle_deg))
                _set(heading, "waypointHeadingPathMode", mission.heading_path_mode)
            _set(place, "useGlobalTurnParam", 1)
            _set(place, "gimbalPitchAngle", 0)
        else:
            _set(place, "executeHeight", _num(mission.altitude_m))
            _set(place, "waypointSpeed", _num(mission.speed_mps))
            heading = ET.SubElement(place, _w("waypointHeadingParam"))
            _set(heading, "waypointHeadingMode", mission.heading_mode)
            if mission.heading_mode == "smoothTransition":
                _set(heading, "waypointHeadingAngle", _num(wp.heading_angle_deg))
                _set(heading, "waypointHeadingPathMode", mission.heading_path_mode)
            turning = ET.SubElement(place, _w("waypointTurnParam"))
            _set(turning, "waypointTurnMode", mission.turn_mode)
            _set(turning, "waypointTurnDampingDist", 0)
        if wp.take_photo:
            _photo_action(place, index, mission.drone_model,
                          legacy_camera_params=legacy_camera_params)
        for seq, action in enumerate(wp.actions, start=1):
            _extra_action(place, index, seq, action, mission.drone_model,
                          legacy_camera_params=legacy_camera_params)
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
    custom_paths: set[str] = set()
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
        # Only the full per-waypoint smooth-yaw profile is editable. Import
        # never guesses omitted angles, yaw paths or mixed heading strategies.
        heading = _w("waypointHeadingParam") + "/"
        heading_mode = txt(point, heading + _w("waypointHeadingMode"))
        use_global = txt(plan, _w("useGlobalHeadingParam"))
        if use_global == "1" and heading_mode == "followWayline":
            heading_angle = None
        elif use_global == "0" and heading_mode == "smoothTransition":
            heading_angle = float(txt(point, heading + _w("waypointHeadingAngle")))
            custom_paths.add(txt(point, heading + _w("waypointHeadingPathMode")))
        else:
            raise ValueError("Unsupported mixed waypoint heading parameters")
        action_groups = point.findall(_w("actionGroup"))
        template_groups = plan.findall(_w("actionGroup"))
        if len(action_groups) != len(template_groups) or len(action_groups) > MAX_WAYPOINT_ACTIONS + 1:
            raise ValueError("Unsupported waypoint action")
        action_names = [g.findtext(_w("action") + "/" + _w("actionActuatorFunc"))
                        for g in action_groups]
        plan_names = [g.findtext(_w("action") + "/" + _w("actionActuatorFunc"))
                      for g in template_groups]
        if action_names != plan_names or action_names.count("takePhoto") > 1:
            raise ValueError("Unsupported waypoint action")
        extra = []
        for group, name in zip(action_groups, action_names):
            if name == "takePhoto":
                continue
            params = group.find(_w("action") + "/" + _w("actionActuatorFuncParam"))
            if params is None:
                raise ValueError("Unsupported waypoint action")
            if name in ("startRecord", "stopRecord"):
                data = {"type": name}
            elif name == "focus":
                data = {"type": name,
                        "focus_x": float(txt(params, _w("focusX"))),
                        "focus_y": float(txt(params, _w("focusY")))}
            elif name == "zoom":
                data = {"type": name,
                        "focal_length_mm": float(txt(params, _w("focalLength")))}
            elif name in ("gimbalRotate", "gimbalEvenlyRotate"):
                data = {"type": name,
                        "pitch_deg": float(txt(params, _w("gimbalPitchRotateAngle")))}
            else:
                raise ValueError("Unsupported waypoint action")
            extra.append(data)
        try:
            lon, lat = (float(coord) for coord in raw.split(","))
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid WGS84 waypoint") from exc
        waypoints.append({"latitude": lat, "longitude": lon,
                          "take_photo": "takePhoto" in action_names,
                          "heading_angle_deg": heading_angle,
                          "actions": extra})
    custom = [wp["heading_angle_deg"] is not None for wp in waypoints]
    if any(custom) and (not all(custom) or len(custom_paths) != 1):
        raise ValueError("Mixed or inconsistent custom heading settings")
    heading_mode = "smoothTransition" if any(custom) else "followWayline"
    heading_path_mode = next(iter(custom_paths)) if any(custom) else None
    turn_mode = txt(route_points[0], _w("waypointTurnParam") + "/" + _w("waypointTurnMode"))
    # AeroNexus exports "close route" as the actual final flight waypoint.
    # Recover the option from that final duplicate only when no camera action
    # would be discarded. Older explicitly repeated finish points may be
    # normalized to the same flight path with a separate reversible switch.
    closed = (
        len(waypoints) >= 4
        and (waypoints[-1]["latitude"], waypoints[-1]["longitude"])
            == (waypoints[0]["latitude"], waypoints[0]["longitude"])
        and not waypoints[-1]["take_photo"]
        and not waypoints[-1].get("actions")
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
        "heading_mode": heading_mode,
        "heading_path_mode": heading_path_mode,
        "turn_mode": turn_mode,
        "close_route": closed,
        "waypoints": waypoints,
    })
    # A supported file must be representable without silently dropping flight
    # semantics. Compare the ENTIRE parsed documents with our own supported
    # representation, including settings, duplicate elements and action params.
    # XML indentation/prefix spelling and the two creation timestamps are not
    # flight semantics. No generic third-party KMZ compatibility is implied.
    for tag in ("createTime", "updateTime"):
        elements = template.findall(_k("Document") + "/" + _w(tag))
        value = (elements[0].text or "").strip() if len(elements) == 1 else ""
        if not value.isascii() or not value.isdigit():
            raise ValueError("Invalid AeroNexus timestamp")
        elements[0].text = "0"
    actual = (_document_signature(template), _document_signature(route))
    # Accept exactly one complete AeroNexus format generation. Mixing old and
    # new camera parameters across documents, or altering any other parameter,
    # is NOT a supported conversion and must never be silently accepted.
    for legacy in (False, True):
        expected = tuple(
            _document_signature(ET.fromstring(
                _xml(mission, template=is_template, timestamp_ms=0,
                     legacy_camera_params=legacy)))
            for is_template in (True, False)
        )
        if actual == expected:
            return mission
    raise ValueError("WPML settings disagree or cannot be preserved by the supported mission format")


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
