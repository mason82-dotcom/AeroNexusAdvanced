"""The separate MQTT decoder observer keeps results anonymous and bounded."""
import importlib.util
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


def test_observer_does_not_log_raw_payload_or_topic():
    code = FILE.read_text()
    assert "print(msg." not in code
    assert "print(serial" not in code
    assert "print(msg.payload" not in code
    assert "client.publish = deny_publish" in code
    assert "client.username_pw_set(settings.username, settings.password)" in code
