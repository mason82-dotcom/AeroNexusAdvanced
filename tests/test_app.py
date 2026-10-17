from fastapi.testclient import TestClient
from aeronexus.app import app

client = TestClient(app)

def test_health():
    assert client.get("/health").json()["status"] == "ok"

def test_three_providers_are_disabled():
    response = client.get("/api/v1/providers")
    assert response.status_code == 200
    providers = response.json()
    assert len(providers) == 3
    assert all(not p["flight_commands_enabled"] for p in providers)

def test_flight_command_is_blocked():
    assert client.post("/api/v1/flight/command").status_code == 403

def test_unknown_provider_is_rejected():
    assert client.get("/api/v1/providers/invalid/status").status_code == 422


def test_provider_diagnostics_use_started_runtime(monkeypatch):
    import importlib
    from types import SimpleNamespace
    from aeronexus.providers import ProviderKind
    module = importlib.import_module("aeronexus.app")
    async def idle(self, stop):
        await stop.wait()
    monkeypatch.setattr(module.ReadOnlyStatusPoller, "run", idle)
    for selected in (ProviderKind.PUBLIC_V2, ProviderKind.ONPREM_V2):
        settings = SimpleNamespace(config=SimpleNamespace(kind=selected), interval_seconds=30)
        monkeypatch.setattr(module.FlightHubPollSettings, "from_env", lambda: settings)
        with TestClient(app) as api:
            providers = api.get("/api/v1/providers").json()
            assert [p["provider"] for p in providers if p["configured"]] == [selected.value]
            assert all(not p["flight_commands_enabled"] for p in providers)
            status = api.get("/api/v1/providers/" + selected.value + "/status").json()
            assert status["configured"] is True


def test_cloud_api2_configuration_is_reported_without_credentials(monkeypatch):
    monkeypatch.setenv("AERONEXUS_CLOUDAPI2_ENABLED", "1")
    monkeypatch.setenv("AERONEXUS_CLOUDAPI2_BFF_URL", "http://127.0.0.1:8080")
    monkeypatch.setenv("AERONEXUS_CLOUDAPI2_BFF_TOKEN", "private-backend-token-0000000000")
    with TestClient(app) as api:
        response = api.get("/api/v1/providers/dji-cloud-api/status")
        assert response.json()["configured"] is True
        assert "private-backend" not in response.text and "8080" not in response.text
    monkeypatch.setenv("AERONEXUS_CLOUDAPI2_ENABLED", "0")
    with TestClient(app) as api:
        assert api.get("/api/v1/providers/dji-cloud-api/status").json()["configured"] is False
