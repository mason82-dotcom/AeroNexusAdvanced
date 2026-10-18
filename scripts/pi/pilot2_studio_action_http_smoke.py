#!/usr/bin/env python3
"""Exercise the real authenticated Studio GET route in-process on the Pi.

NO socket listener, NO app lifespan startup, NO MQTT, NO service restart,
NO writes/uploads/flight commands. The reader makes the same bounded local
GET-only Pilot 2 KMZ requests as the working CLI.

Run from the isolated PR worktree:
    PYTHONPATH=src .venv/bin/python scripts/pi/pilot2_studio_action_http_smoke.py

The temporary dashboard bearer exists only in this Python process. It is
not printed, written to disk, or sent to the upstream DJI Cloud.
"""
import asyncio
import importlib
import json
import os
import secrets
import sys
from unittest.mock import patch

import httpx

from aeronexus.local_waylines import LocalWaylineReader
from aeronexus.pilot2_action_summary import Pilot2ActionSummaryReader


URI = "/api/v1/studio/pilot2/action-summary"
OUTPUT_KEYS = (
    "state", "checked", "total", "recognized_actions", "unknown_actions",
    "read_only", "wpml_semantics_verified", "flight_compatibility_verified",
    "full_content_verified",
)


async def run_smoke(*, transport=None, reader=None):
    """Injectable for offline regression tests; return an anonymous report only."""
    app_module = importlib.import_module("aeronexus.app")
    token = secrets.token_urlsafe(48)
    # This environmental override is process-local and never affects systemd.
    previous_token = os.environ.get("AERONEXUS_STATUS_TOKEN")
    os.environ["AERONEXUS_STATUS_TOKEN"] = token
    previous_reader = getattr(app_module.app.state, "pilot2_action_summary", None)
    summary_reader = reader or Pilot2ActionSummaryReader(LocalWaylineReader())
    app_module.app.state.pilot2_action_summary = summary_reader
    try:
        # The real LAN mode is not tested here. Explicitly exercise bearer
        # enforcement instead of requiring the local HTTP network setup.
        with patch.object(app_module, "lan_mode_enabled", return_value=False):
            async with httpx.AsyncClient(
                transport=transport or httpx.ASGITransport(app=app_module.app),
                base_url="http://127.0.0.1", timeout=110.0,
                follow_redirects=False, trust_env=False,
            ) as client:
                missing = await client.get(URI)
                if missing.status_code != 401:
                    raise RuntimeError("missing bearer was not denied")
                wrong = await client.get(
                    URI, headers={"Authorization": "Bearer invalid-smoke-token"})
                if wrong.status_code != 401:
                    raise RuntimeError("invalid bearer was not denied")
                headers = {"Authorization": "Bearer " + token}
                accepted = await client.get(URI, headers=headers)
                if accepted.status_code != 200:
                    raise RuntimeError("authorized GET was not successful")
                if accepted.headers.get("cache-control") != "no-store":
                    raise RuntimeError("No-Store response header missing")
                report = accepted.json()
                if not isinstance(report, dict):
                    raise RuntimeError("non-object JSON response")
                if report.get("read_only") is not True or any(
                    report.get(k) is not False for k in (
                        "wpml_semantics_verified", "flight_compatibility_verified",
                        "full_content_verified",
                    )
                ):
                    raise RuntimeError("read-only/compatibility boundaries violated")
                if report.get("state") != "connected":
                    # Never forward arbitrary upstream data in failures.
                    raise RuntimeError("live inventory unavailable or incomplete")
                if not 1 <= report.get("checked", 0) <= 8:
                    raise RuntimeError("invalid checked count")
                if not isinstance(report.get("anonymous_types"), list):
                    raise RuntimeError("anonymous types missing")
                if not isinstance(report.get("waylines"), list):
                    raise RuntimeError("wayline summary missing")
                if len(report["waylines"]) != report["checked"]:
                    raise RuntimeError("wayline count mismatch")
                if token in accepted.text:
                    raise RuntimeError("bearer token leaked in HTTP response")
                repeat = await client.get(URI, headers=headers)
                if repeat.status_code != 200 or repeat.json() != report:
                    raise RuntimeError("repeat authorized GET was inconsistent")
                return {key: report.get(key) for key in OUTPUT_KEYS}
    finally:
        if previous_token is None:
            os.environ.pop("AERONEXUS_STATUS_TOKEN", None)
        else:
            os.environ["AERONEXUS_STATUS_TOKEN"] = previous_token
        if previous_reader is None:
            delattr(app_module.app.state, "pilot2_action_summary")
        else:
            app_module.app.state.pilot2_action_summary = previous_reader


def main():
    try:
        report = asyncio.run(run_smoke())
    except (RuntimeError, ValueError, TypeError, httpx.HTTPError) as exc:
        # Do not echo exception messages: transport/upstream details can
        # contain signed URLs, tokens, XML values, or LAN hostnames.
        print("Pilot 2 Studio HTTP smoke: FAIL (" + type(exc).__name__ + ")",
              file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
