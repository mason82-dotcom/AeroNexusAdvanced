"""Safe observer accepts only DJI OSD/state topic shapes and granted SUBACKs."""
import importlib.util
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "scripts" / "pi" / "dji_state_topic_observer.py"


def load():
    spec = importlib.util.spec_from_file_location("dji_state_topic_observer", SRC)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_topic_channel_filter():
    mod = load()
    assert mod.channel_of("thing/product/SAMPLE_DEVICE/osd") == "osd"
    assert mod.channel_of("thing/product/SAMPLE_DEVICE/state") == "state"
    for topic in ("thing/product/+/state", "thing/product/ABC/services",
                  "sys/product/ABC/status", "thing/product/ABC/state_reply",
                  "thing/product/ABC/state/anything", "thing/product//osd", None):
        assert mod.channel_of(topic) is None


def test_ack_must_grant_both_subscriptions():
    mod = load()
    assert mod.granted([0, 0])
    assert mod.granted([0, 1])
    assert not mod.granted([0, 128])
    assert not mod.granted([0])
    assert not mod.granted([])
    assert not mod.granted([0, "invalid"])


def test_no_payload_read_or_persist():
    code = SRC.read_text()
    assert "message.payload" not in code.replace("# No message.payload access.", "")
    assert 'open("w' not in code
