import pytest
from aeronexus.providers import ProviderConfig, ProviderKind
from aeronexus.telemetry import normalize_snapshot

def test_provider_config_redacts_token():
    cfg = ProviderConfig(ProviderKind.PUBLIC_V2, "https://example.com", "very-secret")
    assert "very-secret" not in repr(cfg)
    assert "<redacted>" in repr(cfg)

@pytest.mark.parametrize("url", ["http://example.com", "https://user:pass@example.com", "https://example.com/path"])
def test_provider_rejects_unsafe_url(url):
    with pytest.raises(ValueError):
        ProviderConfig(ProviderKind.ONPREM_V2, url, "secret")

def test_provider_rejects_empty_token():
    with pytest.raises(ValueError):
        ProviderConfig(ProviderKind.PUBLIC_V2, "https://example.com", " ")

def test_normalize_snapshot():
    data = normalize_snapshot(ProviderKind.CLOUD_API, {"device_id": "dock-1", "online": True, "latitude": 49.2, "longitude": 8.5, "battery_percent": 82, "rtk_state": "fixed"})
    assert data.battery_percent == 82
    assert data.rtk_state == "fixed"

@pytest.mark.parametrize("field,value", [("latitude", 91), ("longitude", -181), ("battery_percent", 101), ("latitude", float("nan")), ("online", 1)])
def test_reject_invalid_telemetry(field, value):
    payload = {"device_id": "dock-1", field: value}
    with pytest.raises(ValueError):
        normalize_snapshot(ProviderKind.CLOUD_API, payload)

def test_reject_missing_device_id():
    with pytest.raises(ValueError):
        normalize_snapshot(ProviderKind.PUBLIC_V2, {"online": True})
