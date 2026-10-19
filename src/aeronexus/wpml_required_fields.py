"""Scoped DJI WPML mandatory-field checks for 1.0.2 waypoint KMZ XML.

Offline and read-only. These checks are intentionally independent of the
canonical AeroNexus importer so a missing conditional field has a specific
diagnostic instead of only an opaque round-trip mismatch.

DJI references: template.kml, waylines.wpml, Common Elements. Presence
rules depend on the selected template/actuator. Inconsistencies between
published DJI versions/model rows are NOT silently made flight approvals.
No private XML values, coordinates, indices, names or file paths are returned.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from .wpml_export import KML_NS, WPML_NS

K = "{" + KML_NS + "}"
W = "{" + WPML_NS + "}"
CONTINUOUS = frozenset({
    "toPointAndStopWithContinuityCurvature",
    "toPointAndPassWithContinuityCurvature",
})
TIMED = frozenset({"multipleTiming", "multipleDistance"})
BASE_MISSION = (
    "flyToWaylineMode", "finishAction", "exitOnRCLost",
    "takeOffSecurityHeight", "globalTransitionalSpeed",
)
BASE_GROUP = (
    "actionGroupId", "actionGroupStartIndex", "actionGroupEndIndex",
    "actionGroupMode",
)
# Fields required by supported local actuator types (payloadPositionIndex
# is common to all seven, checked separately). Product-specific lens indices
# are handled by the strict canonical import and the interoperability report.
ACTION_FIELDS = {
    "takePhoto": ("fileSuffix",),
    "startRecord": ("fileSuffix",),
    "stopRecord": (),
    "focus": ("isPointFocus", "focusX", "focusY", "isInfiniteFocus"),
    "zoom": ("focalLength",),
    "gimbalRotate": (
        "gimbalHeadingYawBase", "gimbalRotateMode",
        "gimbalPitchRotateEnable", "gimbalPitchRotateAngle",
        "gimbalRollRotateEnable", "gimbalRollRotateAngle",
        "gimbalYawRotateEnable", "gimbalYawRotateAngle",
        "gimbalRotateTimeEnable", "gimbalRotateTime",
    ),
    "gimbalEvenlyRotate": ("gimbalPitchRotateAngle",),
}


def required_waypoint_findings(
    template: ET.Element, waylines: ET.Element,
) -> list[dict[str, str]]:
    """Check mandatory field *presence* in the local waypoint profile.

    Findings are deduplicated by document/field/severity. The detector does
    not assert full WPML, firmware, lens matrix or flight compatibility.
    Non-waypoint template families are explicitly out of scope.
    """
    findings: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    def missing(doc: str, field: str, conditional: bool = False) -> None:
        kind = "DJI_CONDITIONAL_FIELD_MISSING" if conditional else "DJI_REQUIRED_FIELD_MISSING"
        key = (doc, field, kind)
        if key not in seen:
            seen.add(key)
            findings.append({
                "code": kind,
                "severity": "error",
                "document": doc,
                "field": field,
            })

    def present(node: ET.Element | None, tag: str) -> bool:
        child = node.find(W + tag) if node is not None else None
        return child is not None and child.text is not None and bool(child.text.strip())

    def require(
        node: ET.Element | None, doc: str, *names: str,
        conditional: bool = False,
    ) -> None:
        for name in names:
            if not present(node, name):
                missing(doc, "wpml:" + name, conditional)

    template_type = template.findtext(
        K + "Document/" + K + "Folder/" + W + "templateType"
    )
    # An explicit mapping/strip/oblique template has different obligations;
    # an *absent* type in an AeroNexus-shaped archive is itself an error.
    if template_type not in (None, "", "waypoint"):
        return findings

    for docname, root in (
        ("template.kml", template), ("waylines.wpml", waylines)
    ):
        doc = root.find(K + "Document")
        config = doc.find(W + "missionConfig") if doc is not None else None
        require(config, docname, *BASE_MISSION)
        if config is not None and config.findtext(W + "exitOnRCLost") == "executeLostAction":
            require(config, docname, "executeRCLostAction", conditional=True)
        if docname == "waylines.wpml":
            require(config, docname, "globalRTHHeight")
        require(
            config.find(W + "droneInfo") if config is not None else None,
            docname, "droneEnumValue",
        )
        require(
            config.find(W + "payloadInfo") if config is not None else None,
            docname, "payloadEnumValue", "payloadPositionIndex",
        )
        if config is not None and config.find(W + "autoRerouteInfo") is not None:
            require(config.find(W + "autoRerouteInfo"), docname,
                    "missionAutoRerouteMode", "transitionalAutoRerouteMode",
                    conditional=True)
        if doc is not None and doc.find(K + "Folder/" + W + "payloadParam") is not None:
            require(doc.find(K + "Folder/" + W + "payloadParam"), docname,
                    "payloadPositionIndex", "imageFormat", conditional=True)

        folder = doc.find(K + "Folder") if doc is not None else None
        if docname == "template.kml":
            require(folder, docname, "templateType", "templateId",
                    "autoFlightSpeed", "globalHeight", "gimbalPitchMode",
                    "globalWaypointTurnMode")
            coord = folder.find(W + "waylineCoordinateSysParam") if folder is not None else None
            require(coord, docname, "coordinateMode", "heightMode")
            heading = folder.find(W + "globalWaypointHeadingParam") if folder is not None else None
            if heading is not None:
                require(heading, docname, "waypointHeadingMode")
            if folder is not None and folder.findtext(W + "globalWaypointTurnMode") in CONTINUOUS:
                require(folder, docname, "globalUseStraightLine", conditional=True)
        else:
            require(folder, docname, "templateId", "waylineId",
                    "autoFlightSpeed", "executeHeightMode")

        for point in (folder.findall(K + "Placemark") if folder is not None else ()):
            if point.find(K + "Point/" + K + "coordinates") is None:
                missing(docname, "kml:Point/coordinates")
            require(point, docname, "index")
            if docname == "template.kml":
                require(point, docname, "useGlobalHeight", "useGlobalSpeed",
                        "useGlobalHeadingParam", "useGlobalTurnParam")
                if point.findtext(W + "useGlobalHeight") == "0":
                    require(point, docname, "height", "ellipsoidHeight",
                            conditional=True)
                if point.findtext(W + "useGlobalSpeed") == "0":
                    require(point, docname, "waypointSpeed", conditional=True)
                if folder is not None and folder.findtext(W + "gimbalPitchMode") == "usePointSetting":
                    require(point, docname, "gimbalPitchAngle", conditional=True)
                if point.findtext(W + "useGlobalHeadingParam") == "0":
                    heading = point.find(W + "waypointHeadingParam")
                    require(heading, docname, "waypointHeadingMode",
                            conditional=True)
                    if heading is not None and heading.findtext(W + "waypointHeadingMode") == "smoothTransition":
                        require(heading, docname, "waypointHeadingAngle",
                                conditional=True)
                    if heading is not None and heading.findtext(W + "waypointHeadingMode") == "towardPOI":
                        require(heading, docname, "waypointPoiPoint",
                                conditional=True)
                if point.findtext(W + "useGlobalTurnParam") == "0":
                    turn = point.find(W + "waypointTurnParam")
                    require(turn, docname, "waypointTurnMode", conditional=True)
                turn = point.find(W + "waypointTurnParam")
            else:
                require(point, docname, "executeHeight", "waypointSpeed")
                heading = point.find(W + "waypointHeadingParam")
                turn = point.find(W + "waypointTurnParam")
                require(heading, docname, "waypointHeadingMode")
                require(turn, docname, "waypointTurnMode")
                if heading is not None and heading.findtext(W + "waypointHeadingMode") == "smoothTransition":
                    require(heading, docname, "waypointHeadingAngle",
                            conditional=True)
                if heading is not None and heading.findtext(W + "waypointHeadingMode") == "towardPOI":
                    require(heading, docname, "waypointPoiPoint",
                            conditional=True)
            if turn is not None and turn.findtext(W + "waypointTurnMode") in CONTINUOUS:
                require(point, docname, "useStraightLine", conditional=True)
            if turn is not None and (
                turn.findtext(W + "waypointTurnMode") == "coordinateTurn"
                or (
                    turn.findtext(W + "waypointTurnMode")
                    == "toPointAndPassWithContinuityCurvature"
                    and point.findtext(W + "useStraightLine") == "1"
                )
            ):
                require(turn, docname, "waypointTurnDampingDist", conditional=True)

            for group in point.findall(W + "actionGroup"):
                require(group, docname, *BASE_GROUP)
                trigger = group.find(W + "actionTrigger")
                require(trigger, docname, "actionTriggerType")
                if trigger is not None and trigger.findtext(W + "actionTriggerType") in TIMED:
                    require(trigger, docname, "actionTriggerParam", conditional=True)
                for action in group.findall(W + "action"):
                    require(action, docname, "actionId", "actionActuatorFunc")
                    kind = action.findtext(W + "actionActuatorFunc")
                    params = action.find(W + "actionActuatorFuncParam")
                    if kind in ACTION_FIELDS:
                        require(params, docname, "payloadPositionIndex",
                                *ACTION_FIELDS[kind], conditional=True)
                        if kind == "focus" and params is not None and params.findtext(W + "isPointFocus") == "0":
                            require(params, docname, "focusRegionWidth",
                                    "focusRegionHeight", conditional=True)
    return findings
