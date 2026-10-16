"""Regression: local DJI service secrets/flags must not affect pytest."""
import os

from aeronexus.flighthub_poller import FlightHubPollSettings


def test_live_dji_configuration_does_not_leak_into_tests():
    # This must also pass when the invoking shell exports real DJI settings.
    assert not any(
        name.startswith(("AERONEXUS_DJI_", "AERONEXUS_FH_", "AERONEXUS_CLOUD_MQTT_"))
        or name == "AERONEXUS_STATUS_TOKEN"
        for name in os.environ
    )
    assert FlightHubPollSettings.from_env() is None


def test_explicit_mock_organization_can_still_be_set(monkeypatch):
    monkeypatch.setenv("AERONEXUS_DJI_ORGANIZATION_ID", "ABC123")
    monkeypatch.setenv("AERONEXUS_FH_POLL_ENABLED", "1")
    monkeypatch.setenv("AERONEXUS_DJI_PROVIDER", "public")
    monkeypatch.setenv("AERONEXUS_DJI_BASE_URL", "https://es-flight-api-us.djigate.com")
    monkeypatch.setenv("AERONEXUS_DJI_TOKEN", "not-a-real-token")
    settings = FlightHubPollSettings.from_env()
    assert settings.organization_code == "ABC123"
