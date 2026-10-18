"""The separate MQTT decoder observer keeps results anonymous and bounded."""
import importlib.util
import json

from aeronexus.inventory import DeviceType
from pathlib import Path

FILE = Path(__file__).resolve().parents[1] / "scripts/pi/dji_state_decoder_observer.py"


def _load():
    spec = importlib.util.spec_from_file_location("dji_decoder_observer", FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_suback_grants_both_topics_only():
    m = _load()
    assert m.suback_granted([0, 0])
    assert m.suback_granted([0, 1])
    assert not m.suback_granted([])
    assert not m.suback_granted([0])
    assert not m.suback_granted([0, 128])
    assert not m.suback_granted([0, "invalid"])


def test_outcome_is_one_safe_counter():
    m = _load()
    base = {"accepted": 1, "rejected": 0, "ignored": 3, "outdated": 2}
    for name in ("accepted", "rejected", "ignored"):
        after = dict(base)
        after[name] += 1
        assert m.outcome(base, after) == name
    assert m.outcome(base, dict(base)) == "unclassified"


def test_state_reason_counters_distinguish_missing_osd_and_unsupported():
    mod = _load()
    payload = json.dumps({"data": {"undocumented_marker": 5}}).encode()
    assert mod.categorize(
        None, "state", payload, "ignored", False, 0) == "state_before_osd"
    assert mod.categorize(
        DeviceType.AIRCRAFT, "state", payload, "ignored", False, 0
    ) == "unmapped_properties"
    assert mod.categorize(
        DeviceType.AIRCRAFT, "state", payload, "ignored", True, 0
    ) == "outdated"


def test_state_reason_counters_identify_rejection_classes():
    mod = _load()
    aircraft = DeviceType.AIRCRAFT
    encode = lambda data, **extra: json.dumps({"data": data, **extra}).encode()
    assert mod.categorize(aircraft, "state", b"not json", "rejected", False, 0) == "invalid_envelope"
    assert mod.categorize(aircraft, "state", encode({"rth_mode": 2},
                                                  timestamp=40000),
                          "rejected", False, 0) == "future_source_timestamp"
    assert mod.categorize(aircraft, "state", encode({"capacity_percent": 60}),
                          "rejected", False, 0) == "kind_conflict"
    assert mod.categorize(aircraft, "state", encode({"rth_altitude": 800}),
                          "rejected", False, 0) == "invalid_field"
    assert mod.categorize(aircraft, "state", encode({"rth_mode": 2}),
                          "accepted", False, 0) is None


def test_reason_labels_are_bounded_fixed_strings():
    mod = _load()
    assert len(mod.REASONS) == len(set(mod.REASONS))
    assert "invalid_field" in mod.REASONS
    assert "outdated" in mod.REASONS
    assert all(reason.isidentifier() for reason in mod.REASONS)


def test_observer_does_not_log_raw_payload_or_topic():
    code = FILE.read_text()
    assert "print(msg." not in code
    assert "print(serial" not in code
    assert "print(msg.payload" not in code
    assert "client.publish = deny_publish" in code
    assert "client.username_pw_set(settings.username, settings.password)" in code
