"""Isolation of simulated DJI tests from the Pi's live service environment.

The user's shell may export a real FlightHub organization code, token, region,
project selection or enable flags. They must never leak into tests, whose
fixtures explicitly opt in to fake provider settings with monkeypatch.setenv.

This fixture changes only the current test's os.environ; pytest restores the
original environment after every test. Production runtime code is untouched.
"""
import os

import pytest


_LIVE_PREFIXES = ("AERONEXUS_DJI_", "AERONEXUS_FH_", "AERONEXUS_CLOUD_MQTT_")
_LIVE_KEYS = frozenset({"AERONEXUS_STATUS_TOKEN", "AERONEXUS_LAN_NO_TOKEN", "AERONEXUS_LAN_HOST"})


@pytest.fixture(autouse=True)
def isolate_live_service_environment(monkeypatch):
    """Avoid test-order dependencies and unintended real-service access."""
    for key in tuple(os.environ):
        if key.startswith(_LIVE_PREFIXES) or key in _LIVE_KEYS:
            monkeypatch.delenv(key)
