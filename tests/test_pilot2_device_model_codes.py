"""DJI Pilot 2 model codes: full Mavic 3 Enterprise family and strict topology decoding."""
import pytest

from aeronexus.pilot2_readonly import _device, _device_model_key, _topology_payload
from aeronexus.studio_page import render_studio
from aeronexus.wpml_export import MODELS


AIRCRAFT = {
    "0-77-0": ("mavic3e", (77, 0, 66, 0)),
    "0-77-1": ("mavic3t", (77, 1, 67, 0)),
    "0-77-2": ("mavic3m", (77, 2, 68, 0)),
    "0-77-3": ("mavic3ta", (77, 3, 129, 0)),
}
CONTROLLERS = {
    "2-144-0": "DJI RC Pro Enterprise",
    "2-174-0": "DJI RC Plus 2",
}


@pytest.mark.parametrize("code,profile", AIRCRAFT.items())
def test_all_mavic_3_enterprise_models_from_cloud_components(code, profile):
    values = code.split("-")
    model = {"domain": values[0], "type": int(values[1]), "sub_type": values[2]}
    assert _device_model_key(model, "aircraft") == code
    name, expected_wpml = profile
    assert MODELS[name] == expected_wpml


@pytest.mark.parametrize("code", CONTROLLERS)
def test_controllers_from_cloud_components(code):
    domain, kind, variant = code.split("-")
    assert _device_model_key(
        {"domain": int(domain), "type": kind, "sub_type": int(variant)},
        "controller",
    ) == code


@pytest.mark.parametrize("role,code", [
    ("aircraft", *tuple(AIRCRAFT)[0:1]),
    ("controller", "2-144-0"),
    ("controller", "2-174-0"),
    ("aircraft", "0-99-1"),
])
def test_explicit_key_keeps_working(role, code):
    assert _device_model_key({"key": code}, role) == code


@pytest.mark.parametrize("code", AIRCRAFT)
def test_matching_key_and_fields(code):
    d, t, s = code.split("-")
    assert _device_model_key(
        {"key": code, "domain": d, "type": t, "sub_type": int(s)},
        "aircraft",
    ) == code


@pytest.mark.parametrize("model", [
    None,
    "0-77-0",
    {},
    {"domain": "0", "type": 77},
    {"domain": 0, "type": True, "sub_type": 0},
    {"domain": 0, "type": -77, "sub_type": 0},
    {"domain": 0, "type": 100000, "sub_type": 0},
    {"domain": 0, "type": "77a", "sub_type": 0},
    {"domain": 0, "type": 77, "sub_type": 0.0},
    {"domain": 0, "type": 77, "sub_type": 100000},
    {"key": "0-77-0", "domain": 0, "type": 77, "sub_type": 1},
    {"key": "bad-key", "domain": 0, "type": 77, "sub_type": 0},
    {"key": "0-77-0", "domain": 2},
])
def test_invalid_or_contradictory_aircraft_model_fails_closed(model):
    assert _device_model_key(model, "aircraft") is None


def test_aircraft_code_cannot_be_used_as_controller_model():
    assert _device_model_key({"key": "0-77-0"}, "controller") is None
    assert _device_model_key(
        {"domain": 2, "type": 144, "sub_type": 0}, "aircraft"
    ) is None


def test_partial_fields_must_match_valid_key():
    assert _device_model_key(
        {"key": "0-77-2", "domain": 0}, "aircraft"
    ) == "0-77-2"
    assert _device_model_key(
        {"key": "0-77-2", "type": 99}, "aircraft"
    ) is None


def test_topology_does_not_need_key_and_keeps_same_response_schema():
    code = "0-77-2"
    response = _device({
        "sn": "TEST-SYNTHETIC-123",
        "device_model": {"domain": 0, "type": 77, "sub_type": 2},
        "online_status": False,
    }, "aircraft")
    assert response["device_model_key"] == code
    assert set(response) == {
        "serial_number", "role", "device_model_key", "callsign", "online"
    }
    assert response["online"] is False
    assert _device({
        "sn": "TEST-SYNTHETIC-456",
        "device_model": {"domain": 2, "type": 144, "sub_type": 0},
    }, "controller")["device_model_key"] == "2-144-0"


def test_existing_matrice_model_still_supported():
    assert _device_model_key(
        {"domain": 0, "type": 99, "sub_type": 1}, "aircraft"
    ) == "0-99-1"


def test_browser_labels_cover_all_mavic_3_family_and_rcs():
    page = render_studio()
    for code in AIRCRAFT:
        assert '"'+code+'"' in page
    for code, label in CONTROLLERS.items():
        assert '"'+code+'":"'+label+'"' in page
    assert "const modelLabel=waylineModel(item.device_model_key);" in page


def test_empty_map_payload_does_not_grant_flight_compatibility():
    # Model recognition concerns viewer metadata only, not waypoint approval.
    import aeronexus.pilot2_readonly as readonly
    parsed = readonly._map_payload([])
    assert parsed["features"] == []
    assert parsed["complete"] is True
    assert "flight_compatibility_verified" not in parsed
