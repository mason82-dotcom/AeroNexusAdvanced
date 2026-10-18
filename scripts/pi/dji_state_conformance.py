#!/usr/bin/env python3
"""Read-only, privacy-preserving M4T / RC Plus 2 DJI MQTT-state acceptance probe.

Reads the *existing* protected AeroNexus status API over verified HTTPS.
No MQTT publishing, subscription changes, DJI commands, raw payloads, SNs,
positions, account tokens or telemetry values are printed or stored.
"""
import argparse
import json
import os
from pathlib import Path
import ssl
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPSHandler, Request, build_opener, HTTPRedirectHandler


# Expected = useful conformance observations, NOT guaranteed capabilities.
# All strings are fixed canonical property paths, never taken from DJI payloads.
EXPECTED = {
    "aircraft": {
        "osd": (
            "flight_mode_code", "latitude", "longitude", "elevation_m",
            "battery_percent", "gps_satellites", "rtk_state",
            "cloud_details.heading_deg", "cloud_details.wind_speed_mps",
            "cloud_details.position.quality_code",
            "cloud_details.distance_limit.state_code",
            "cloud_details.distance_limit.distance_limit_m",
        ),
        "state": (
            "cloud_details.control_source_category",
            "cloud_details.home_latitude", "cloud_details.home_longitude",
            "cloud_details.firmware_version",
            "cloud_details.firmware_compatible_status_code",
            "cloud_details.firmware_upgrade_status_code",
            "cloud_details.low_battery_warning_percent",
            "cloud_details.critical_battery_warning_percent",
            "cloud_details.payload_control",
        ),
    },
    "controller": {
        "osd": (
            "battery_percent", "latitude", "longitude",
            "cloud_details.controller_height_m",
            "cloud_details.drc_link_state_code",
            "cloud_details.wireless_link.sdr_link_state_code",
            "cloud_details.wireless_link.sdr_quality",
        ),
        "state": (
            "cloud_details.firmware_version",
            "cloud_details.cloud_control_authorization_count",
            "cloud_details.live_status", "cloud_details.live_capacity.available_videos",
            "cloud_details.live_capacity.simultaneous_videos",
        ),
    },
}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def origin(value):
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.path not in ("", "/") or parsed.query
            or parsed.fragment):
        raise ValueError("Only a plain HTTPS origin is permitted")
    return value.rstrip("/")


def _read_json(opener, endpoint, token):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    with opener.open(Request(endpoint, headers=headers, method="GET"), timeout=8) as response:
        raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("Status response exceeds 1 MiB")
        body = json.loads(raw)
    if not isinstance(body, dict):
        raise ValueError("Status response is not a JSON object")
    return body


def empty_capture():
    return {kind: {channel: set() for channel in ("osd", "state")} for kind in EXPECTED}


def accumulate(capture, devices):
    """Consume field clocks only; never read serials, positions or actual values."""
    if not isinstance(devices, list):
        raise ValueError("Device response must contain a list")
    counts = {kind: 0 for kind in EXPECTED}
    for device in devices:
        if not isinstance(device, dict) or device.get("provider") != "dji-cloud-api":
            continue
        kind = device.get("kind")
        if kind not in EXPECTED:
            continue
        counts[kind] += 1
        fields = device.get("field_status") or {}
        if not isinstance(fields, dict):
            continue
        for channel in ("osd", "state"):
            allowed = EXPECTED[kind][channel]
            for path in allowed:
                # An entire array is represented by its field clock, not by its data.
                info = fields.get(path)
                if isinstance(info, dict) and info.get("channel") == channel:
                    capture[kind][channel].add(path)
    return counts


def sanitize_channels(feed):
    result = {}
    channels = feed.get("channels", {})
    for channel in ("osd", "state"):
        source = channels.get(channel, {}) if isinstance(channels, dict) else {}
        counts = {}
        for key in ("accepted", "rejected", "ignored", "outdated"):
            value = source.get(key) if isinstance(source, dict) else None
            counts[key] = value if type(value) is int and value >= 0 else None
        result[channel] = counts
    return result


def report(capture, maximum_devices, summary, baseline=None):
    feed = summary.get("live_feed") or {}
    if not isinstance(feed, dict):
        feed = {}
    channel_counts = sanitize_channels(feed)
    coverage = {}
    for kind in EXPECTED:
        coverage[kind] = {"devices_seen": maximum_devices[kind]}
        for channel in ("osd", "state"):
            seen = capture[kind][channel]
            coverage[kind][channel] = {
                "observed": sorted(seen),
                "not_observed": sorted(set(EXPECTED[kind][channel]) - seen),
            }
    state_enabled = feed.get("state_topic_enabled") is True
    start = sanitize_channels(baseline.get("live_feed", {})) if baseline else channel_counts
    delta = {}
    for channel in ("osd", "state"):
        before, after = start[channel]["accepted"], channel_counts[channel]["accepted"]
        delta[channel] = (max(after - before, 0) if before is not None
                          and after is not None and after >= before else None)
    state_count = delta["state"]
    if not maximum_devices["aircraft"] or not maximum_devices["controller"]:
        outcome = "missing_aircraft_or_controller"
    elif not state_enabled:
        outcome = "state_subscription_disabled"
    elif state_count is None:
        outcome = "channel_counters_unavailable_deploy_branch_first"
    elif state_count == 0:
        outcome = "state_event_not_observed_in_window"
    else:
        outcome = "state_events_observed_in_window_partial_property_evidence"
    return {
        "scope": "DJI Cloud API 1.18, M4T / RC Plus 2 candidate properties",
        "evidence": "live API field clocks; no hardware values retained",
        "feed_state": feed.get("state") if feed.get("state") in (
            "subscribed", "connected", "connecting", "stopped", "disabled",
            "subscription_denied", "auth_failed", "unreachable", "disconnected") else "unknown",
        "state_topic_enabled": state_enabled,
        "channels": channel_counts,
        "accepted_during_observation": delta,
        "coverage": coverage,
        "outcome": outcome,
        "notice": "Not observed does not imply unsupported: state is change-triggered. "
                  "A decoded property does not establish aircraft identity or flight authorization.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True,
                        help="Existing AeroNexus HTTPS origin, e.g. https://LAN-IP:8000")
    parser.add_argument("--ca", required=True, type=Path,
                        help="Local certificate authority PEM for verified HTTPS")
    parser.add_argument("--seconds", type=int, default=60,
                        help="Observation time, 0..600 s (default 60)")
    parser.add_argument("--lan-without-token", action="store_true",
                        help="Allow the existing HTTPS-LAN authentication mode without a bearer token")
    args = parser.parse_args(argv)
    try:
        base = origin(args.base_url)
        if not 0 <= args.seconds <= 600:
            raise ValueError("seconds must be between 0 and 600")
        token = os.environ.get("AERONEXUS_STATUS_TOKEN", "")
        if not token and not args.lan_without_token:
            raise ValueError("Set AERONEXUS_STATUS_TOKEN, or explicitly use --lan-without-token")
        context = ssl.create_default_context(cafile=str(args.ca))
        opener = build_opener(HTTPSHandler(context=context), NoRedirect())
        capture = empty_capture()
        maximum = {kind: 0 for kind in EXPECTED}
        end_at = time.monotonic() + args.seconds
        summary = {}
        baseline = _read_json(opener, base + "/api/v1/status/summary", token)
        while True:
            summary = _read_json(opener, base + "/api/v1/status/summary", token)
            devices = _read_json(opener, base + "/api/v1/status/devices?limit=200", token)
            counts = accumulate(capture, devices.get("devices"))
            for kind in EXPECTED:
                maximum[kind] = max(maximum[kind], counts[kind])
            if time.monotonic() >= end_at:
                break
            time.sleep(min(5, max(0, end_at - time.monotonic())))
        print(json.dumps(report(capture, maximum, summary, baseline), indent=2, sort_keys=True))
        return 0
    except HTTPError as exc:
        print(f"Read-only API request failed: HTTP {exc.code}", file=sys.stderr)
    except (OSError, URLError, ValueError, json.JSONDecodeError) as exc:
        # No error response body, URL, credentials or raw data is printed.
        print(f"Read-only API probe failed ({type(exc).__name__})", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
