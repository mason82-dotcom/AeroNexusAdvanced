"""Read-only API gateway. No remote flight operations are exposed."""
from enum import Enum
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="AeroNexusAdvanced", version="0.1.0")

class Provider(str, Enum):
    public_v2 = "flighthub-public-v2"
    onprem_v2 = "flighthub-onprem-v2"
    cloud_api = "dji-cloud-api"

class ProviderStatus(BaseModel):
    provider: Provider
    configured: bool = False
    flight_commands_enabled: bool = False

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "aeronexusadvanced"}

@app.get("/api/v1/providers", response_model=list[ProviderStatus])
def providers() -> list[ProviderStatus]:
    return [ProviderStatus(provider=provider) for provider in Provider]

@app.get("/api/v1/providers/{provider}/status", response_model=ProviderStatus)
def provider_status(provider: Provider) -> ProviderStatus:
    return ProviderStatus(provider=provider)

@app.post("/api/v1/flight/command", status_code=403)
def blocked_flight_command() -> None:
    raise HTTPException(status_code=403, detail="Flight commands disabled by default")
