"""Explicit provider configuration. No network calls and no secret disclosure."""
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

class ProviderKind(StrEnum):
    PUBLIC_V2 = "flighthub-public-v2"
    ONPREM_V2 = "flighthub-onprem-v2"
    CLOUD_API = "dji-cloud-api"

@dataclass(frozen=True, repr=False)
class ProviderConfig:
    kind: ProviderKind
    base_url: str
    access_token: str

    def __post_init__(self):
        parts = urlsplit(self.base_url)
        if (parts.scheme != "https" or not parts.hostname or parts.username
                or parts.password or parts.path not in ("", "/") or parts.query or parts.fragment):
            raise ValueError("Provider base_url must be an HTTPS origin")
        if not self.access_token.strip():
            raise ValueError("Provider access token must not be empty")

    def __repr__(self):
        return f"ProviderConfig(kind={self.kind.value!r}, base_url={self.base_url!r}, access_token='<redacted>')"

@dataclass(frozen=True)
class DeviceSnapshot:
    provider: ProviderKind
    device_id: str
    online: bool | None = None
    latitude: float | None = None
    longitude: float | None = None
    battery_percent: float | None = None
    rtk_state: str | None = None
