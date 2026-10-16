"""Conservative offline DJI WPML waypoint KMZ exporter.

Reference: DJI Cloud API WPML template.kml, waylines.wpml, product support.
Only waypoint routes for Matrice 4T/4E; no upload, execution or flight API.
Heights are uniform, relative to actual takeoff point. Per-waypoint ellipsoid
heights require surveyed elevation data and are intentionally not guessed.
"""
from io import BytesIO
from math import isfinite
from zipfile import ZIP_DEFLATED, ZipFile
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
}


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
    drone_model: Literal["matrice4t", "matrice4e"] = "matrice4t"
    altitude_m: float = Field(default=50.0, ge=2.0, le=500)
    speed_mps: float = Field(default=5.0, gt=0, le=15)
    takeoff_security_height_m: float = Field(default=20.0, ge=1.2, le=1500)
    rth_height_m: float = Field(default=60.0, ge=2, le=500)
    finish_action: Literal["goHome", "noAction"] = "goHome"
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
    for index, wp in enumerate(mission.waypoints):
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
    if not 2 <= len(mission.waypoints) <= 500:
        raise ValueError("WPML export requires between 2 and 500 waypoints")
    if timestamp_ms < 0:
        raise ValueError("Invalid timestamp")
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("wpmz/template.kml", _xml(mission, template=True, timestamp_ms=timestamp_ms))
        archive.writestr("wpmz/waylines.wpml", _xml(mission, template=False, timestamp_ms=timestamp_ms))
    return buffer.getvalue()
