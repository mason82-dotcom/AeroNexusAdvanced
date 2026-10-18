#!/usr/bin/env python3
"""Observe incoming DJI MQTT state using the canonical decoder in isolated RAM.

Independent read-only MQTT connection; reproduces the current production
CloudOsdIngest decoder. No service restart, command publishing, disk capture,
serials, positions, or actual property values in output. All payloads are
handled in process memory only and discarded after each callback.
"""
import argparse
from collections import Counter
from pathlib import Path
import secrets
import sys
import threading
import time


def suback_granted(codes):
    if len(codes) != 2:
        return False
    try:
        return all(int(getattr(code, "value", code)) in (0, 1, 2) for code in codes)
    except (ValueError, TypeError):
        return False


def outcome(before, after):
    """Translate a decoder-counter change into one non-sensitive result."""
    for name in ("accepted", "rejected", "ignored"):
        if after[name] > before[name]:
            return name
    return "unclassified"


def snapshot(ingest):
    return {name: getattr(ingest, name) for name in
            ("accepted", "rejected", "ignored", "outdated")}


# Fixed, non-sensitive labels. Never log original key names, topics or payload.
REASONS = ("outdated", "state_before_osd", "unmapped_properties",
           "invalid_envelope", "future_source_timestamp", "kind_conflict",
           "invalid_field", "other")


def categorize(known_kind, channel, payload, verdict, outdated, now_ms):
    """Independently classify one decoder outcome without exposing DJI values.

    Called only *after* the canonical decoder has made its decision.
    A category is diagnostic, not an additional decoder acceptance rule.
    """
    if verdict == "accepted":
        return None
    if verdict == "ignored" and outdated:
        return "outdated"
    if verdict == "ignored" and channel == "state" and known_kind is None:
        return "state_before_osd"

    from aeronexus.cloud_api_osd import classify, normalize_osd, osd_envelope

    try:
        data, timestamp = osd_envelope(payload)
    except ValueError:
        return "invalid_envelope" if verdict == "rejected" else "other"
    if verdict == "rejected" and timestamp is not None and timestamp > now_ms + 30000:
        return "future_source_timestamp"
    classified = classify(data)
    if known_kind is not None and classified is not None and classified != known_kind:
        return "kind_conflict" if verdict == "rejected" else "other"
    kind = known_kind if known_kind is not None else classified
    if kind is None:
        return "other"
    try:
        fields = normalize_osd(kind, data)
    except ValueError:
        return "invalid_field" if verdict == "rejected" else "other"
    if verdict == "ignored" and not fields:
        return "unmapped_properties"
    return "other"


# Fixed categories: only check allowlisted outer DJI property names.
# The reader does not output unknown names, nested content, serials or values.
_UNMAPPED_ROOTS = (
    ("rc_video_capability_only", frozenset(("live_capacity",))),
    ("rc_stream_state_only", frozenset(("live_status",))),
    ("aircraft_psdk_ui", frozenset(("psdk_ui_resource",))),
    ("aircraft_psdk_widgets", frozenset(("psdk_widget_values",))),
    ("aircraft_payload_control_only", frozenset(("payloads",))),
    ("sensitive_dongle_metadata", frozenset(("dongle_infos",))),
    ("rc_link_metadata_only", frozenset(("wireless_link",))),
    ("aircraft_battery_metadata_only", frozenset(("battery",))),
    ("aircraft_maintenance_metadata_only", frozenset(("maintain_status",))),
)
UNMAPPED_BUCKETS = tuple(label for label, _ in _UNMAPPED_ROOTS) + ("other_or_unknown",)


def unmapped_bucket(payload):
    """One bounded, fixed diagnostic label; never return user-supplied keys."""
    from aeronexus.cloud_api_osd import osd_envelope
    try:
        data, _timestamp = osd_envelope(payload)
    except ValueError:
        return "other_or_unknown"
    keys = data.keys()
    for label, approved in _UNMAPPED_ROOTS:
        if any(key in keys for key in approved):
            return label
    return "other_or_unknown"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--seconds", type=int, default=120)
    args = parser.parse_args(argv)
    if not 1 <= args.seconds <= 600:
        parser.error("--seconds must be between 1 and 600")

    try:
        import paho.mqtt.client as mqtt
        from dotenv import dotenv_values
        from aeronexus.cloud_api_mqtt import CloudOsdIngest, MqttSettings
        from aeronexus.cloud_api_osd import MAX_PAYLOAD_BYTES, topic_device
        from aeronexus.providers import ProviderKind
        from aeronexus.status_runtime import StatusRuntime

        if args.env_file.stat().st_mode & 0o077:
            raise ValueError("The private .env must have mode 0600")
        config = {k: v for k, v in dotenv_values(args.env_file).items()
                  if v is not None}
        settings = MqttSettings.from_env(config)
        if (settings is None or not settings.include_state
                or settings.username != "aeronexus_osd"):
            raise ValueError("Only an enabled, dedicated read-only state observer is allowed")

        # Isolated, in-memory decoder: never touches the production runtime,
        # API or inventory. Only approved OSD/state topics are subscribed.
        ingest = CloudOsdIngest(StatusRuntime(), project_id=settings.project_id)
        received = Counter()
        outcomes = Counter()
        recognized = Counter()
        subscribed = threading.Event()
        flags = {"granted": False, "interrupted": False, "stopping": False}

        def on_connect(client, _userdata, _flags, reason, _properties=None):
            if int(getattr(reason, "value", reason)) != 0:
                subscribed.set()
                return
            result, _mid = client.subscribe([
                ("thing/product/+/osd", 0),
                ("thing/product/+/state", 0),
            ])
            if result != mqtt.MQTT_ERR_SUCCESS:
                subscribed.set()

        def on_subscribe(_client, _userdata, _mid, codes, _properties=None):
            flags["granted"] = suback_granted(codes)
            subscribed.set()

        def on_message(_client, _userdata, msg):
            try:
                serial, channel = topic_device(msg.topic)
                if channel not in ("osd", "state"):
                    return
                received[channel] += 1
                if not isinstance(msg.payload, bytes) or len(msg.payload) > MAX_PAYLOAD_BYTES:
                    outcomes[channel, "rejected_oversize"] += 1
                    return

                from datetime import datetime, timezone
                known = ingest.runtime.inventory._devices.get(
                    (ProviderKind.CLOUD_API, settings.project_id, serial))
                known_kind = known.kind if known is not None else None
                before = snapshot(ingest)
                # The production decoder is reused unmodified, but runs only
                # against an isolated in-memory inventory in this observer.
                ingest.handle(msg.topic, msg.payload, allow_state=True)
                after = snapshot(ingest)
                result = outcome(before, after)
                outcomes[channel, result] += 1
                is_outdated = after["outdated"] > before["outdated"]
                if is_outdated:
                    outcomes[channel, "outdated"] += 1
                if result in ("ignored", "rejected"):
                    try:
                        reason = categorize(
                            known_kind, channel, msg.payload, result, is_outdated,
                            int(datetime.now(timezone.utc).timestamp() * 1000),
                        )
                        if channel == "state" and reason == "unmapped_properties":
                            # These buckets are fixed labels, not dynamic DJI data.
                            bucket = unmapped_bucket(msg.payload)
                            outcomes["state", "unmapped_" + bucket] += 1
                    except (TypeError, ValueError):
                        reason = "other"
                    outcomes[channel, "reason_" + reason] += 1
                if channel == "state" and result == "accepted":
                    device = ingest.runtime.inventory._devices.get(
                        (ProviderKind.CLOUD_API, settings.project_id, serial))
                    if device:
                        recognized[device.kind.value] += 1
            except Exception:
                # Never leak exception text or incoming payloads.
                outcomes["internal_errors"] += 1

        def on_disconnect(_client, _userdata, _flags, _reason, _properties=None):
            if not flags["stopping"]:
                flags["interrupted"] = True

        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="aeronexus-decoder-audit-" + secrets.token_hex(5),
            clean_session=True,
        )

        def deny_publish(*_args, **_kwargs):
            raise PermissionError("Read-only MQTT observer")

        client.publish = deny_publish
        client.username_pw_set(settings.username, settings.password)
        if settings.tls:
            client.tls_set()
        client.on_connect = on_connect
        client.on_subscribe = on_subscribe
        client.on_message = on_message
        client.on_disconnect = on_disconnect
        client.connect(settings.host, settings.port, keepalive=30)
        client.loop_start()
        try:
            if not subscribed.wait(timeout=12) or not flags["granted"]:
                print("subscription_granted: False")
                return 2
            print("subscription_granted: True", flush=True)
            time.sleep(args.seconds)
        finally:
            flags["stopping"] = True
            client.disconnect()
            client.loop_stop()

        print("=== Read-only canonical DJI decoder audit ===")
        for channel in ("osd", "state"):
            print(f"{channel}_messages:", received[channel])
            for metric in ("accepted", "ignored", "rejected", "rejected_oversize",
                           "outdated", "unclassified"):
                print(f"{channel}_{metric}:", outcomes[channel, metric])
        print("=== DJI state decoder outcome reasons (privacy-safe) ===")
        for name in REASONS:
            print(f"state_reason_{name}:", outcomes["state", "reason_" + name])
        print("=== State unmapped-property categories (safe fixed labels) ===")
        for name in UNMAPPED_BUCKETS:
            print(f"state_unmapped_{name}:", outcomes["state", "unmapped_" + name])
        print("state_accepted_aircraft:", recognized["aircraft"])
        print("state_accepted_controller:", recognized["controller"])
        state_clocks = {
            k: v for (provider, _, _serial), clocks in
            ingest.runtime.cloud_field_clocks.items()
            if provider == ProviderKind.CLOUD_API
            for k, v in clocks.items()
            if v.get("channel") == "state"
        }
        # Counts only; never log device IDs, dynamic paths or payload values.
        print("state_distinct_field_paths:", len(state_clocks))
        print("connection_interrupted:", flags["interrupted"])
        print("internal_errors:", outcomes["internal_errors"])
        print("No credentials, serial numbers, positions or values printed or saved.")
        return 0 if outcomes["internal_errors"] == 0 else 2
    except (OSError, ValueError, ImportError, ConnectionError) as exc:
        print(f"Decoder observer failed ({type(exc).__name__})", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
