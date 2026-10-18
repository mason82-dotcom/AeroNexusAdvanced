"""Read-only DJI WPML action taxonomy, not an execution/flight allowlist.

Only explicitly named DJI WPML actions can appear here. Pilot 2 observations
identify enum labels but DO NOT verify XML 1.0.6 parameter semantics, aircraft
firmware support, action-group timing, safe replay or flight compatibility.
"""
from types import MappingProxyType

# Documented DJI Cloud API WPML actionActuatorFunc enums.
DOCUMENTED_ACTION_LABELS = MappingProxyType({
    "takePhoto": "Foto aufnehmen",
    "startRecord": "Videoaufzeichnung starten",
    "stopRecord": "Videoaufzeichnung stoppen",
    "focus": "Fokus einstellen",
    "zoom": "Zoom einstellen",
    "customDirName": "Medienordner benennen",
    "gimbalRotate": "Gimbal drehen",
    "rotateYaw": "Fluggerät drehen (Gierwinkel)",
    "hover": "Schweben",
    "gimbalEvenlyRotate": "Gimbal gleichmäßig drehen",
    "accurateShoot": "Präzisionsaufnahme (veraltet)",
    "orientedShoot": "Gerichtete Fotoaufnahme",
    "panoShot": "Panoramaaufnahme",
    "recordPointCloud": "Punktwolken-Aufzeichnung",
})

# These seven names were observed in eight genuine DJI Pilot 2 WPML 1.0.6
# archives. Labels describe the likely intent only; parameters remain unverified.
PILOT2_OBSERVED_ACTIONS = MappingProxyType({
    "setFocusType": ("Kamera-Fokusmodus", "focus"),
    "startSmartOblique": ("Smart Oblique starten", "smart_oblique"),
    "stopSmartOblique": ("Smart Oblique stoppen", "smart_oblique"),
    "startContinuousShooting": ("Serienaufnahmen starten", "continuous_shooting"),
    "stopContinuousShooting": ("Serienaufnahmen stoppen", "continuous_shooting"),
    "startTimeLapse": ("Intervallaufnahme starten", "time_lapse"),
    "stopTimeLapse": ("Intervallaufnahme stoppen", "time_lapse"),
})

# Fixed, bounded list of extra field names observed in the user's data.
# No guesses about their values, ranges, units or semantics.
PILOT2_OBSERVED_FIELDS = frozenset({
    "cameraFocusType", "smartObliqueCycleMode",
    "smartObliquePoint", "minShootInterval",
})

OFFLINE_WPML_EXPORT_ACTIONS = frozenset({
    "takePhoto", "startRecord", "stopRecord", "focus", "zoom",
    "gimbalRotate", "gimbalEvenlyRotate",
})


def public_documented_catalog():
    """Only immutable locally defined labels and capabilities (no raw XML)."""
    return [
        {"name": key, "label": label, "status": "documented",
         "export_supported": key in OFFLINE_WPML_EXPORT_ACTIONS}
        for key, label in DOCUMENTED_ACTION_LABELS.items()
    ]

def public_pilot2_catalog():
    return [
        {"name": key, "label": data[0], "family": data[1],
         "status": "pilot2_observed_unverified", "export_supported": False}
        for key, data in PILOT2_OBSERVED_ACTIONS.items()
    ]
