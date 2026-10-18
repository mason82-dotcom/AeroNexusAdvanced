#!/usr/bin/env python3
"""Count DJI MQTT OSD/state topics without opening or retaining message payloads.

Read-only, independent subscriber using the production observer's dedicated,
non-superuser MQTT account. Prints no topic names, device IDs, message
payloads, credentials, coordinates or telemetry values. Never publishes.
"""

import argparse
from collections import Counter
from pathlib import Path
import re
import secrets
import sys
import threading
import time


_TOPIC = re.compile(r"thing/product/[A-Za-z0-9_-]{1,80}/(osd|state)\Z")
_TOPICS = (("thing/product/+/osd", 0), ("thing/product/+/state", 0))


def channel_of(topic):
    match = _TOPIC.fullmatch(topic) if isinstance(topic, str) else None
    return match.group(1) if match else None


def granted(codes):
    if len(codes) != 2:
        return False
    try:
        return all(int(getattr(code, "value", code)) in (0, 1, 2) for code in codes)
    except (TypeError, ValueError):
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True, type=Path,
                        help="Existing, private AeroNexusAdvanced .env")
    parser.add_argument("--seconds", type=int, default=120,
                        help="Observation duration 1..600 seconds")
    args = parser.parse_args(argv)
    if not 1 <= args.seconds <= 600:
        parser.error("--seconds must be between 1 and 600")
    try:
        from dotenv import dotenv_values
        import paho.mqtt.client as mqtt
        from aeronexus.cloud_api_mqtt import MqttSettings

        if args.env_file.stat().st_mode & 0o077:
            raise ValueError(".env permissions must be private (0600)")
        env = {k: v for k, v in dotenv_values(args.env_file).items() if v is not None}
        settings = MqttSettings.from_env(env)
        if settings is None or not settings.include_state:
            raise ValueError("DJI MQTT feed and explicit state opt-in must be enabled")
        if settings.username != "aeronexus_osd":
            raise ValueError("Only the non-superuser aeronexus_osd observer is permitted")

        ack = threading.Event()
        messages = Counter(osd=0, state=0)
        status = {"granted": False, "disconnected": False, "stopping": False}

        def on_connect(client, _userdata, _flags, reason_code, _properties=None):
            if int(getattr(reason_code, "value", reason_code)) != 0:
                ack.set()
                return
            code, _mid = client.subscribe(list(_TOPICS))
            if code != mqtt.MQTT_ERR_SUCCESS:
                ack.set()

        def on_subscribe(_client, _userdata, _mid, reason_codes, _properties=None):
            status["granted"] = granted(reason_codes)
            ack.set()

        def on_message(_client, _userdata, message):
            # No message.payload access. Never print or retain the device topic.
            channel = channel_of(message.topic)
            if channel is not None:
                messages[channel] += 1

        def on_disconnect(_client, _userdata, _flags, _reason_code, _properties=None):
            if not status["stopping"]:
                status["disconnected"] = True

        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="aeronexus-state-audit-" + secrets.token_hex(5),
            clean_session=True,
        )
        def forbid_publish(*_args, **_kwargs):
            raise PermissionError("MQTT publishing is disabled")

        client.publish = forbid_publish
        client.username_pw_set(settings.username, settings.password)
        if settings.tls:
            client.tls_set()  # verify broker certificate with system CA
        client.on_connect = on_connect
        client.on_subscribe = on_subscribe
        client.on_message = on_message
        client.on_disconnect = on_disconnect
        client.connect(settings.host, settings.port, keepalive=30)
        client.loop_start()
        try:
            if not ack.wait(timeout=12) or not status["granted"]:
                print("subscription_granted: False")
                return 2
            print("subscription_granted: True", flush=True)
            time.sleep(args.seconds)
        finally:
            status["stopping"] = True
            client.disconnect()
            client.loop_stop()

        print("=== DJI MQTT topic counts during observation ===")
        print("osd_messages:", messages["osd"])
        print("state_messages:", messages["state"])
        print("connection_interrupted:", status["disconnected"])
        print("No payloads, serial numbers, coordinates or credentials accessed.")
        return 0
    except (OSError, ValueError, ImportError) as exc:
        # Errors are deliberately type-only: never echo environment or secrets.
        print(f"Read-only MQTT observation failed ({type(exc).__name__})", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
