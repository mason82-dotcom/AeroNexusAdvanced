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

                before = snapshot(ingest)
                # The production decoder is reused unmodified, but runs only
                # against an isolated in-memory inventory in this observer.
                ingest.handle(msg.topic, msg.payload, allow_state=True)
                after = snapshot(ingest)
                result = outcome(before, after)
                outcomes[channel, result] += 1
                if after["outdated"] > before["outdated"]:
                    outcomes[channel, "outdated"] += 1
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
