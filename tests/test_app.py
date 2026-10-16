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
