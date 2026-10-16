"""Explicit provider configuration. No network calls and no secret disclosure."""
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

# Public Cloud gateways. An organization key only works on the gateway of the
# region that issued it (the other one answers 401). "eu" is not in DJI's
# OpenAPI pages; it was verified live by alecad/dji-flighthub2-cli (Apache-2.0).
REGIONS = {
    "eu": "https://es-flight-api-eu.djigate.com",
    "us": "https://es-flight-api-us.djigate.com",
    "cn": "https://es-flight-api-cn.djigate.com",
}
# v2.0: current DJI reference. v0.1: previous reference with the same Public
# Cloud paths (project, project/device, device/{sn}/state, device/hms),
# validated live on the EU gateway by dji-flighthub2-cli.
API_VERSIONS = ("v2.0", "v0.1")


class ProviderKind(StrEnum):
    PUBLIC_V2 = "flighthub-public-v2"
    ONPREM_V2 = "flighthub-onprem-v2"
    CLOUD_API = "dji-cloud-api"

@dataclass(frozen=True, repr=False)
class ProviderConfig:
    kind: ProviderKind
    base_url: str
    access_token: str
    api_version: str = "v2.0"

    def __post_init__(self):
        parts = urlsplit(self.base_url)
        if (parts.scheme != "https" or not parts.hostname or parts.username
                or parts.password or parts.path not in ("", "/") or parts.query or parts.fragment):
            raise ValueError("Provider base_url must be an HTTPS origin")
        if not self.access_token.strip():
            raise ValueError("Provider access token must not be empty")
        if self.api_version not in API_VERSIONS:
            raise ValueError("Unsupported OpenAPI version")
        if self.kind == ProviderKind.ONPREM_V2 and self.api_version != "v2.0":
            raise ValueError("On-Premises supports OpenAPI v2.0 only")

    def path(self, suffix: str) -> str:
        """Versioned OpenAPI path, e.g. path("/project") -> /openapi/v2.0/project."""
        if not suffix.startswith("/"):
            raise ValueError("API path suffix must start with /")
        return f"/openapi/{self.api_version}{suffix}"

    def __repr__(self):
        return (f"ProviderConfig(kind={self.kind.value!r}, base_url={self.base_url!r}, "
                f"api_version={self.api_version!r}, access_token='<redacted>')")

@dataclass(frozen=True)
class DeviceSnapshot:
    provider: ProviderKind
    device_id: str
    online: bool | None = None
    latitude: float | None = None
    longitude: float | None = None
    battery_percent: float | None = None
    rtk_state: str | None = None
    height_m: float | None = None
    horizontal_speed_mps: float | None = None
    vertical_speed_mps: float | None = None
    total_flight_time_s: float | None = None
    total_flight_sorties: int | None = None
    rtk_satellites: int | None = None
    gps_satellites: int | None = None
    battery_voltage_mv: float | None = None
    battery_temperature_c: float | None = None
    # DJI Cloud API OSD (Pilot 2 via MQTT): height above take-off point,
    # distance to home point and the raw DJI flight mode code.
    elevation_m: float | None = None
    home_distance_m: float | None = None
    flight_mode_code: int | None = None
