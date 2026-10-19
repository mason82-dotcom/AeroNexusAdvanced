"""DJI Pilot-to-Cloud /state data={} contract (offline, no MQTT broker)."""

import json
import time

import pytest

from aeronexus.cloud_api_mqtt import CloudOsdIngest
from aeronexus.cloud_api_osd import CloudOsdError, osd_data, osd_envelope, topic_device
from aeronexus.providers import ProviderKind
from aeronexus.status_runtime import StatusRuntime


AIRCRAFT = "SYNTHETIC_M4T"
OSD = f"thing/product/{AIRCRAFT}/osd"
STATE = f"thing/product/{AIRCRAFT}/state"


def message(data, *, timestamp=None):
    # DJI's documented common envelope. All identifiers are synthetic.
    return json.dumps({
        "tid": "synthetic-transaction",
        "bid": "synthetic-business",
        "gateway": "SYNTHETIC_RC",
        "timestamp": int(time.time() * 1000) if timestamp is None else timestamp,
        "data": data,
    }).encode("utf-8")


def test_empty_state_example_parses_only_with_explicit_opt_in():
    payload = message({})
    parsed, stamp = osd_envelope(payload, allow_empty_data=True)
    assert parsed == {} and type(stamp) is int
    with pytest.raises(CloudOsdError):
        osd_envelope(payload)
    with pytest.raises(CloudOsdError):
        osd_data(payload)


def test_empty_state_of_unknown_device_is_ignored_not_registered():
    ingest = CloudOsdIngest(StatusRuntime())
    assert not ingest.handle(STATE, message({}), allow_state=True)
    assert (ingest.accepted, ingest.rejected, ingest.ignored) == (0, 0, 1)
    assert ingest.channel_counters["state"]["ignored"] == 1
    assert not ingest.runtime.inventory.devices()
    assert ingest.last_message_at is None


def test_empty_state_preserves_existing_telemetry_and_liveness():
    ingest = CloudOsdIngest(StatusRuntime())
    assert ingest.handle(OSD, message({"mode_code": 3, "height": 6.2}))
    key = (ProviderKind.CLOUD_API, "aeronexus", AIRCRAFT)
    inv = ingest.runtime.inventory
    original = inv.telemetry(*key)
    osd_clock = dict(ingest.runtime.cloud_osd_clocks[key])
    field_clocks = dict(ingest.runtime.cloud_field_clocks[key])
    received_at = inv._received_at[key]
    last_message_at = ingest.last_message_at

    assert not ingest.handle(STATE, message({}), allow_state=True)
    assert inv.telemetry(*key) == original
    assert inv._received_at[key] == received_at
    assert ingest.runtime.cloud_osd_clocks[key] == osd_clock
    assert ingest.runtime.cloud_field_clocks[key] == field_clocks
    assert ingest.last_message_at == last_message_at
    assert (ingest.accepted, ingest.rejected, ingest.ignored) == (1, 0, 1)
    assert ingest.channel_counters["state"]["ignored"] == 1
    assert ingest.channel_counters["state"]["accepted"] == 0
    assert ingest.channel_counters["state"]["last_message_at"] is None


def test_state_opt_in_still_required_even_for_empty_envelope():
    ingest = CloudOsdIngest(StatusRuntime())
    assert not ingest.handle(STATE, message({}))
    assert (ingest.accepted, ingest.rejected, ingest.ignored) == (0, 1, 0)
    assert ingest.channel_counters["state"]["rejected"] == 1


@pytest.mark.parametrize("bad_payload", [
    b'{"data":null}',
    b'{"data":[]}',
    b'{"timestamp":true,"data":{}}',
    b'{"data":',
])
def test_invalid_state_envelopes_remain_rejected(bad_payload):
    ingest = CloudOsdIngest(StatusRuntime())
    assert not ingest.handle(STATE, bad_payload, allow_state=True)
    assert (ingest.accepted, ingest.rejected, ingest.ignored) == (0, 1, 0)


def test_empty_state_with_future_timestamp_is_rejected():
    ingest = CloudOsdIngest(StatusRuntime())
    assert not ingest.handle(STATE, message({}, timestamp=int(time.time() * 1000) + 60000),
                             allow_state=True)
    assert (ingest.accepted, ingest.rejected, ingest.ignored) == (0, 1, 0)


@pytest.mark.parametrize("forbidden_topic", [
    "thing/product/SYNTHETIC_M4T/services",
    "thing/product/SYNTHETIC_M4T/property/set",
    "thing/product/SYNTHETIC_M4T/drc/down",
    "thing/product/SYNTHETIC_M4T/events_reply",
    "sys/product/SYNTHETIC_M4T/status",
])
def test_command_and_secret_bearing_topics_are_not_telemetry(forbidden_topic):
    with pytest.raises(CloudOsdError):
        topic_device(forbidden_topic)
    ingest = CloudOsdIngest(StatusRuntime())
    assert not ingest.handle(forbidden_topic, message({}), allow_state=True)
    assert (ingest.accepted, ingest.rejected, ingest.ignored) == (0, 1, 0)
